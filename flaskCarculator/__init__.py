import gc
import os

from flask import Flask


def create_app():
    app = Flask(__name__)

    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = None
    app.config["JSON_SORT_KEYS"] = False
    app.json.sort_keys = False

    from .routes import main as main_blueprint

    app.register_blueprint(main_blueprint)

    @app.after_request
    def free_memory(response):
        gc.collect()
        return response

    return app


def main():
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
