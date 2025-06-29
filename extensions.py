# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
import redis

# Create extension instances
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
# socketio = SocketIO(cors_allowed_origins="*")
socketio = SocketIO(cors_allowed_origins=["http://localhost:5000", "http://127.0.0.1:5000"])

# Simple wrapper for Redis to work with the app factory pattern
class FlaskRedis:
    def __init__(self, app=None):
        self._redis_client = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        redis_url = app.config.get('REDIS_URL')
        if redis_url:
            self._redis_client = redis.from_url(redis_url, decode_responses=True)

    def __getattr__(self, name):
        # This makes it so you can call redis_client.get(), .set(), etc.
        return getattr(self._redis_client, name)

redis_client = FlaskRedis()