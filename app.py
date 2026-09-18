from datetime import datetime
from routes.search_routes import search_bp
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from routes.email_routes import email_bp
from config import Config
from routes.application_routes import application_bp
from routes.auth_routes import auth_bp
from routes.document_routes import document_bp
from routes.profile_routes import profile_bp
from routes.programme_routes import programme_bp
from routes.saved_routes import saved_bp
from routes.university_routes import university_bp
from services.auth_decorators import current_user
from routes.admin_routes import admin_bp

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

    # ----- Template context processors -----
    @app.context_processor
    def inject_globals():
        """Variables available to every template."""
        return {
            "current_year": datetime.now().year,
            "current_user": current_user(),
        }

    # ----- Blueprints -----
    app.register_blueprint(search_bp)        # /search
    app.register_blueprint(auth_bp)          # /register, /login, /logout, /dashboard
    app.register_blueprint(admin_bp)         # /admin
    app.register_blueprint(profile_bp)       # /profile
    app.register_blueprint(university_bp)    # /universities, /universities/<id>
    app.register_blueprint(programme_bp)     # /programmes/<id>, save/unsave
    app.register_blueprint(saved_bp)         # /saved
    app.register_blueprint(application_bp)   # /applications
    app.register_blueprint(document_bp)      # /documents
    app.register_blueprint(email_bp)         # /emails
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

    # ----- Global Supabase JWT-expired handling -----
    from services.session_refresh import is_jwt_expired_error, refresh_access_token as _refresh

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        from flask import flash, redirect, request, session as flask_session, url_for
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