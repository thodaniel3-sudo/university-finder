


# BSA_fakekey_testing_secret_scanner_1234567890abcdef


from datetime import datetime

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from routes.discovery_routes import discovery_bp
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
from services.auth_decorators import current_user
from services.rate_limit import limiter


def create_app(config_class=Config):
    """Application factory. Returns a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ----- Extensions -----
    # CSRFProtect enables {{ csrf_token() }} in every template
    # AND automatically rejects unsafe HTTP methods (POST/PUT/DELETE)
    # that don't carry a valid token.
    csrf = CSRFProtect()
    csrf.init_app(app)

    
    # The discovery save endpoint accepts JSON from the search page.
    # It is not a session-state-changing form, so it is exempt from CSRF.
    from routes.discovery_routes import discovery_bp as _discovery_bp
    csrf.exempt(_discovery_bp)

    # Rate limiter — per-route limits are applied via @limiter.limit()
    limiter.init_app(app)



    # ----- CORS for the Vercel frontend -----
    # The Vercel site is on a different origin than Render. Without these
    # headers the browser blocks every API request. We allow only the
    # origins we control.
    from flask import request as _request

    ALLOWED_ORIGINS = {
        "http://localhost:5000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5000",
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

    @app.route("/api/v1/<path:_any>", methods=["OPTIONS"])
    def api_options(_any):
        """Preflight requests for the JSON API."""
        return ("", 204)


    # ----- Template context processors -----
    @app.context_processor
    def inject_globals():
        """Variables available to every template."""
        return {
            "current_year": datetime.now().year,
            "current_user": current_user(),
        }

    # ----- Blueprints -----
    app.register_blueprint(auth_bp)          # /register, /login, /logout, /dashboard
    app.register_blueprint(admin_bp)         # /admin
    app.register_blueprint(profile_bp)       # /profile
    app.register_blueprint(university_bp)    # /universities, /universities/<id>
    app.register_blueprint(programme_bp)     # /programmes/<id>, save/unsave
    app.register_blueprint(saved_bp)         # /saved
    app.register_blueprint(application_bp)   # /applications
    app.register_blueprint(document_bp)      # /documents
    app.register_blueprint(email_bp)         # /emails
    app.register_blueprint(external_bp)      # /external/*
    app.register_blueprint(search_bp)        # /search
    app.register_blueprint(facebook_bp)      # /facebook/connect, /callback, /status
    app.register_blueprint(discovery_bp)


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

    # ----- Global Supabase JWT-expired handling -----
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

        # Let HTTP exceptions (404, 403, etc.) pass through.
        if isinstance(exc, HTTPException):
            return exc

        # If this is a Supabase JWT-expired error, try to refresh and retry.
        if is_jwt_expired_error(exc) and flask_session.get("refresh_token"):
            if _refresh():
                return redirect(request.full_path)
            flask_session.clear()
            flash("Your session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

        # Anything else: re-raise so Flask's normal error handling shows.
        raise exc from None

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)