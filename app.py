from flask import Flask
from flaskCarculator.routes import main

def create_app():
    app = Flask(__name__)

    # Register the blueprint
    app.register_blueprint(main)

    # App configurations
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_TYPE'] = None  # Disable session entirely

    # Memory cleanup
    import gc
    @app.after_request
    def free_memory(response):
        gc.collect()
        return response

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
