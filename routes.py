# routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from models import User, Room
from forms import LoginForm, RegistrationForm
from extensions import db, redis_client
import json
import logging

# A Blueprint is a way to organize a group of related views.
# We name it 'main' here.
main_bp = Blueprint('main', __name__)

# --- Helper Functions for Redis (move them here or keep in a separate utils.py) ---
def get_room_data(room):
    if not redis_client: return None
    room_data_json = redis_client.get(f"room:{room}")
    if room_data_json:
        return json.loads(room_data_json)
    return None

def initialize_room(room_id):
    # This function is now called every time the room page is loaded, ensuring
    # Redis is always populated before a socket connection attempts to read from it.
    if get_room_data(room_id) is None:
        room_db_obj = Room.query.filter_by(name=room_id).first()
        if not room_db_obj:
            logging.error(f"Attempted to initialize a non-existent room in Redis: {room_id}")
            return # Should not happen if called from the room route which does a first_or_404
        
        initial_videos = json.loads(room_db_obj.videos) if room_db_obj and room_db_obj.videos else []
        new_room = {
            'users': [], 'queue': initial_videos,
            'current_video_index': -1 if not initial_videos else 0,
            'state': 'PAUSED', 'time': 0
        }
        redis_client.set(f"room:{room_id}", json.dumps(new_room))
        logging.info(f"Initialized room in Redis from DB: '{room_id}'")

# --- All web routes go here, using @main_bp.route instead of @app.route ---

@main_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        if room_name:
            if Room.query.filter_by(name=room_name).first():
                flash('A room with this name already exists. Please choose another.')
            else:
                new_room = Room(name=room_name, owner=current_user)
                db.session.add(new_room)
                db.session.commit()
                # Initialize in Redis immediately upon creation
                initialize_room(room_name)
                flash(f'Room "{room_name}" created!')
                return redirect(url_for('main.room', room_id=room_name))
    user_rooms = current_user.rooms.all()
    return render_template('index.html', title='Dashboard', user_rooms=user_rooms)

@main_bp.route('/room/<room_id>')
@login_required
def room(room_id):
    # This line correctly verifies the room exists in our main database.
    room_obj = Room.query.filter_by(name=room_id).first_or_404()
    
    # *** THIS IS THE FIX ***
    # Ensure the room is initialized in Redis before rendering the page.
    # This prevents the race condition where the client's socket tries to join
    # a room that doesn't exist in Redis yet. The initialize_room function
    # already checks if the room is active, so it's safe to call here.
    initialize_room(room_id)
    
    # Now, when the client connects, the room data will be ready in Redis.
    return render_template('room.html', room_id=room_id, room_name=room_obj.name)
    
    return render_template('room.html', room_id=room_id, room_name=room_obj.name)

@main_bp.route('/room/<room_id>/delete', methods=['POST'])
@login_required
def delete_room(room_id):
    room_to_delete = Room.query.filter_by(name=room_id).first_or_404()
    if room_to_delete.owner != current_user:
        flash("You do not have permission to delete this room.")
        return redirect(url_for('main.index')), 403
    if redis_client:
        redis_client.delete(f"room:{room_id}")
    db.session.delete(room_to_delete)
    db.session.commit()
    flash(f'Room "{room_id}" has been deleted.')
    return redirect(url_for('main.index'))

# --- Login/Logout/Register routes remain the same ---

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('main.login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('main.index'))
    return render_template('login.html', title='Sign In', form=form)

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)