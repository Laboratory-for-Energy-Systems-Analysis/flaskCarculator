import os
from flaskCarculator import create_app

if __name__ == '__main__':
    app = create_app()
    # Use the PORT environment variable provided by Heroku
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
