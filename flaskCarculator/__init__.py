# my_flask_app/__init__.py
from flask import Flask


def create_app():
    app = Flask(__name__)

    # Configure your app
    app.config.from_object('config.Config')

    # Register routes or blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

