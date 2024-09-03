from flask import Flask
from flaskCarculator.routes import main

app = Flask(__name__)

# Register the blueprint
app.register_blueprint(main)

if __name__ == '__main__':
    app.run(debug=True)
