from flask import Flask
from flaskCarculator.routes import main


app = Flask(__name__)

# Register the blueprint
app.register_blueprint(main)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = None  # Disable session entirely

if __name__ == '__main__':
    app.run(debug=True)
