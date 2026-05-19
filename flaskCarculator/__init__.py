import gc
import os

from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge


def _get_int_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def create_app():
    app = Flask(__name__)

    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = None
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = _get_int_env("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)
    app.config["MAX_VEHICLES_PER_REQUEST"] = _get_int_env("MAX_VEHICLES_PER_REQUEST", 25)
    app.json.sort_keys = False

    from .routes import main as main_blueprint

    app.register_blueprint(main_blueprint)

    @app.errorhandler(RequestEntityTooLarge)
    def request_entity_too_large(error):
        max_content_length = app.config.get("MAX_CONTENT_LENGTH")
        return jsonify(
            {
                "error": "Request body too large",
                "details": [
                    f"Request body must be smaller than {max_content_length} bytes."
                ],
            }
        ), 413

    @app.after_request
    def free_memory(response):
        gc.collect()
        return response

    return app


def main():
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
