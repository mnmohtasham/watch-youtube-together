# socket_events.py
from flask import request
from flask_login import current_user
from extensions import socketio, redis_client
from flask_socketio import emit, join_room, leave_room
import json
import logging

# --- Helper Functions (remain the same) ---
def get_room_data(room):
    """Fetches room data from Redis."""
    if not redis_client: return None
    room_data_json = redis_client.get(f"room:{room}")
    return json.loads(room_data_json) if room_data_json else None

def set_room_data(room, data):
    """Saves room data to Redis."""
    if not redis_client: return
    redis_client.set(f"room:{room}", json.dumps(data))

def play_video_at_index(room_id, index, room_data=None):
    """Changes the currently playing video and notifies clients."""
    if room_data is None:
        room_data = get_room_data(room_id)
    if room_data and 0 <= index < len(room_data['queue']):
        room_data.update({'current_video_index': index, 'state': 'PLAYING', 'time': 0})
        set_room_data(room_id, room_data)
        video_info = room_data['queue'][index]
        logging.info(f"Room '{room_id}' is now playing video at index {index}: {video_info['id']}")
        emit('state_change', {
            'event': 'load_video', 'video_id': video_info['id'],
            'current_video_index': index, 'time': 0, 'state': 'PLAYING'
        }, to=room_id)

# --- Socket Event Handlers ---

sid_to_user = {}

@socketio.on('join')
def on_join(data):
    """Handles a user joining a room."""
    if not current_user.is_authenticated:
        return

    username = current_user.username
    room_id = data.get('room')
    if not room_id:
        return
    
    # With the fix in routes.py, this check should now always pass for valid rooms.
    room_data = get_room_data(room_id)
    if not room_data:
        logging.warning(f"User '{username}' tried to join room '{room_id}' which is not in Redis.")
        # Optionally, you could try to initialize it here as a fallback.
        # from routes import initialize_room
        # initialize_room(room_id)
        # room_data = get_room_data(room_id)
        # if not room_data: return
        return

    join_room(room_id)
    sid_to_user[request.sid] = {'username': username, 'room': room_id}

    user_set = set(room_data.get('users', []))
    user_set.add(username)
    room_data['users'] = list(user_set)
    set_room_data(room_id, room_data)

    logging.info(f"'{username}' ({request.sid}) has joined room '{room_id}'")
    
    emit('user_list_update', {'users': room_data['users']}, to=room_id)
    
    emit('sync_state', {
        'queue': room_data.get('queue', []),
        'current_video_index': room_data.get('current_video_index', -1),
        'state': room_data.get('state', 'PAUSED'),
        'time': room_data.get('time', 0)
    }, to=request.sid)

# 'add_to_queue' and 'play_specific_video' handlers remain the same.
@socketio.on('add_to_queue')
def on_add_to_queue(data):
    room_id = data.get('room')
    room_data = get_room_data(room_id)
    if not room_data or not current_user.is_authenticated: return
    video_info = {'id': data.get('video_id'), 'title': data.get('video_title', 'Untitled')}
    room_data['queue'].append(video_info)
    if room_data['current_video_index'] == -1 and len(room_data['queue']) > 0:
        play_video_at_index(room_id, 0, room_data)
    else:
        set_room_data(room_id, room_data)
    emit('queue_update', {'queue': room_data['queue']}, to=room_id)

@socketio.on('play_specific_video')
def on_play_specific_video(data):
    room_id = data.get('room')
    if not get_room_data(room_id) or not current_user.is_authenticated: return
    play_video_at_index(room_id, data.get('index'))


@socketio.on('player_event')
def on_player_event(data):
    """Handles player events like play, pause, seek, and video end."""
    room_id = data.get('room')
    room_data = get_room_data(room_id)
    if not room_data or not current_user.is_authenticated:
        return

    event_type = data['event']
    
    # *** FIX: More explicit handling for seek event ***
    if event_type == 'play':
        room_data['state'] = 'PLAYING'
        room_data['time'] = data.get('time', room_data.get('time', 0)) # Update time on play
        set_room_data(room_id, room_data)
        emit('state_change', {'event': 'play', 'time': room_data['time']}, to=room_id, include_self=False)

    elif event_type == 'pause':
        room_data['state'] = 'PAUSED'
        room_data['time'] = data.get('time', 0)
        set_room_data(room_id, room_data)
        emit('state_change', {'event': 'pause', 'time': room_data['time']}, to=room_id, include_self=False)
        
    elif event_type == 'seek':
        room_data['time'] = data.get('time', 0)
        # The state (PLAYING/PAUSED) doesn't change on seek, just the time.
        set_room_data(room_id, room_data)
        # Broadcast the specific seek event to others.
        emit('state_change', {'event': 'seek', 'time': room_data['time']}, to=room_id, include_self=False)

    elif event_type == 'video_ended':
        next_index = room_data['current_video_index'] + 1
        if 0 <= next_index < len(room_data['queue']):
            play_video_at_index(room_id, next_index, room_data)
        else: 
            room_data['state'] = 'PAUSED'
            set_room_data(room_id, room_data)
            # Notify clients that the queue has ended.
            emit('state_change', {'event': 'queue_ended'}, to=room_id)

@socketio.on('add_to_queue')
def on_add_to_queue(data):
    room_id = data.get('room')
    room_data = get_room_data(room_id)
    if not room_data or not current_user.is_authenticated: return
    
    video_info = {'id': data.get('video_id'), 'title': data.get('video_title', 'Untitled')}
    room_data['queue'].append(video_info)
    
    if room_data['current_video_index'] == -1 and len(room_data['queue']) > 0:
        # play_video_at_index also calls set_room_data, so we don't need to do it twice
        play_video_at_index(room_id, 0, room_data)
    else:
        set_room_data(room_id, room_data)
        
    # *** ADD THIS BLOCK TO PERSIST THE QUEUE ***
    try:
        room_db_obj = Room.query.filter_by(name=room_id).first()
        if room_db_obj:
            room_db_obj.videos = json.dumps(room_data['queue'])
            db.session.commit()
            logging.info(f"Persisted queue for room '{room_id}' to database.")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to persist queue for room '{room_id}': {e}")
    # *** END OF NEW BLOCK ***

    emit('queue_update', {'queue': room_data['queue']}, to=room_id)


# 'disconnect' handler remains the same.
@socketio.on('disconnect')
def on_disconnect():
    user_info = sid_to_user.pop(request.sid, None)
    if user_info:
        username = user_info['username']
        room_id = user_info['room']
        leave_room(room_id)
        room_data = get_room_data(room_id)
        if room_data and 'users' in room_data and username in room_data['users']:
            # Check if this is the last connection for that user
            is_last_connection = not any(
                u['username'] == username for u in sid_to_user.values()
            )
            if is_last_connection:
                room_data['users'].remove(username)
                set_room_data(room_id, room_data)
                emit('user_list_update', {'users': room_data['users']}, to=room_id)
        logging.info(f"'{username}' ({request.sid}) has left room '{room_id}'")
    else:
        logging.info(f'Client disconnected: {request.sid} (was not in a registered room)')