from datetime import datetime

from flask import Flask, jsonify, render_template

from config import Config
from services.supabase_service import get_public_client


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
        }

    # ----- Public routes -----
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    # ----- Temporary diagnostic route (remove in Phase 9) -----
    @app.route("/_dbcheck")
    def db_check():
        """
        Confirms the Flask app can reach Supabase and read from the
        universities table. Returns JSON. Will be removed once real
        search routes exist.
        """
        try:
            client = get_public_client()
            response = (
                client.table("universities")
                .select("id, name, country", count="exact")
                .limit(5)
                .execute()
            )
            return jsonify({
                "ok": True,
                "count": response.count,
                "rows": response.data,
            })
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)