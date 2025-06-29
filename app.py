# app.py
import logging
import redis
from flask import Flask
from config import Config
from extensions import db, migrate, login, redis_client, socketio

def create_app(config_class=Config):
    # --- Basic App Setup ---
    app = Flask(__name__)
    app.config.from_object(config_class)
    logging.basicConfig(level=logging.INFO)

    # --- Initialize Extensions with the App ---
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'main.login'
    socketio.init_app(app)
    
    try:
        redis_client.init_app(app)
        redis_client.ping()
        logging.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Could not connect to Redis: {e}")
        pass

    # --- Import and Register Blueprints ---
    from routes import main_bp
    app.register_blueprint(main_bp)

    # The models need to be known to Flask-Migrate
    with app.app_context():
        from models import User, Room

    return app

# The app object needs to be available globally for Flask CLI and Gunicorn
app = create_app()
import socket_events
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)