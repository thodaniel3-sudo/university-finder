from datetime import datetime

from flask import Flask, render_template

from config import Config


def create_app(config_class=Config):
    """Application factory. Returns a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ----- Template context processors -----
    @app.context_processor
    def inject_globals():
        """
        Make these variables available to every template
        without passing them from each route.
        """
        return {
            "current_year": datetime.now().year,
        }

    # ----- Routes -----
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
