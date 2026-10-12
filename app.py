# BSA_fakekey_testing_secret_scanner_1234567890abcdef


from datetime import datetime

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from config import Config

from routes.admin_routes import admin_bp
from routes.application_routes import application_bp
from routes.auth_routes import auth_bp
from routes.document_routes import document_bp
from routes.email_routes import email_bp
from routes.external_routes import external_bp
from routes.facebook_routes import facebook_bp
from routes.profile_routes import profile_bp
from routes.programme_routes import programme_bp
from routes.saved_routes import saved_bp
from routes.search_routes import search_bp
from routes.university_routes import university_bp
from routes.discovery_routes import discovery_bp
from routes.reddit_routes import reddit_bp
from routes.aggregated_sources_routes import aggregated_bp
from routes.apify_sources_routes import apify_bp
from routes.extra_sources_routes import extra_bp

from services.auth_decorators import current_user
from services.rate_limit import limiter


def create_app(config_class=Config):
    """Application factory. Returns a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ----- Trust X-Forwarded-* headers from Vercel -----
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=0,
    )

    # ----- Extensions -----
    csrf = CSRFProtect()
    csrf.init_app(app)

    csrf.exempt(discovery_bp)
    csrf.exempt(apify_bp)
    csrf.exempt(facebook_bp)

    limiter.init_app(app)

    # ----- CORS for the Vercel frontend -----
    from flask import request as _request, redirect as _redirect

    ALLOWED_ORIGINS = {
        "http://localhost:5000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5000",
        "https://university-finder.me",
        "https://www.university-finder.me",
        "https://university-finder-database.onrender.com",
        "https://university-finder-frontend.vercel.app",
    }

    @app.after_request
    def add_cors_headers(response):
        origin = _request.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-CSRFToken, Authorization"
            )
            response.headers["Vary"] = "Origin"
        return response

    # ----- Redirect Render hostname to real domain -----
    @app.before_request
    def redirect_render_host():
        host = (_request.host or "").lower()
        if host.endswith(".onrender.com"):
            preferred = app.config.get("PREFERRED_HOST", "")
            if preferred and _request.method in ("GET", "HEAD"):
                return _redirect(preferred + _request.full_path, code=301)
        return None

    # ----- Redirect www to non-www -----
    @app.before_request
    def redirect_www():
        host = (_request.host or "").lower()
        if host == "www.university-finder.me":
            preferred = app.config.get("PREFERRED_HOST", "")
            if preferred and _request.method in ("GET", "HEAD"):
                return _redirect(preferred + _request.full_path, code=301)
        return None

    # ----- API preflight -----
    @app.route("/api/v1/<path:_any>", methods=["OPTIONS"])
    def api_options(_any):
        return ("", 204)

    # ----- Context processors -----
    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.now().year,
            "current_user": current_user(),
            "preferred_host": app.config.get("PREFERRED_HOST", ""),
        }

    # ----- Blueprints (each registered exactly once) -----
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(university_bp)
    app.register_blueprint(programme_bp)
    app.register_blueprint(saved_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(external_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(facebook_bp)
    app.register_blueprint(discovery_bp)
    app.register_blueprint(reddit_bp)
    app.register_blueprint(aggregated_bp)
    app.register_blueprint(apify_bp)
    app.register_blueprint(extra_bp)

    # ----- Public routes -----
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    # ----- Error handlers -----
    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return render_template("429.html"), 429

    # ----- Supabase JWT-expired handling -----
    from services.session_refresh import (
        is_jwt_expired_error,
        refresh_access_token as _refresh,
    )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        from flask import (
            flash,
            redirect,
            request,
            session as flask_session,
            url_for,
        )
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc

        if is_jwt_expired_error(exc) and flask_session.get("refresh_token"):
            if _refresh():
                return redirect(request.full_path)
            flask_session.clear()
            flash("Your session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

        raise exc from None

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)