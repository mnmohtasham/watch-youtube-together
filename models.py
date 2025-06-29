# models.py
from extensions import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# The 'user_loader' callback is used to reload the user object
# from the user ID stored in the session.
@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    # This relationship links a User to all their Rooms
    rooms = db.relationship('Room', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    # The owner_id links this room to a specific user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # We will store the video queue persistently here
    videos = db.Column(db.Text, default='[]') # Storing as a JSON string

    def __repr__(self):
        return f'<Room {self.name}>'