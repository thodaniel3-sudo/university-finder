from datetime import datetime

from flask import Flask, render_template

from config import Config
from routes.auth_routes import auth_bp
from routes.profile_routes import profile_bp
from routes.university_routes import university_bp
from services.auth_decorators import current_user


def create_app(config_class=Config):
    """Application factory. Returns a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

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
    app.register_blueprint(profile_bp)       # /profile
    app.register_blueprint(university_bp)    # /universities, /universities/<id>

    # ----- Public routes -----
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)