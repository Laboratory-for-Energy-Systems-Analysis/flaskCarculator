from flask import Flask
from flaskCarculator.routes import main

def create_app():
    app = Flask(__name__)

    # Register the blueprint
    app.register_blueprint(main)

    # App configurations
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_TYPE'] = None  # Disable session entirely
    app.config['JSON_SORT_KEYS'] = False

    # Memory cleanup
    import gc
    @app.after_request
    def free_memory(response):
        gc.collect()
        return response

    return app

if __name__ == '__main__':
    app = create_app()
    # Use the PORT environment variable provided by Heroku
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
