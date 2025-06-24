# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import logging
import uuid  # ## NEW FEATURE: To generate unique room IDs if none is provided

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key!'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for room states
rooms = {}


# ## NEW FEATURE: Route to handle joining via a direct link
@app.route('/room/<room_id>')
def room(room_id):
    """Serve the index page for a specific room."""
    return render_template('index.html', room_id=room_id)


@app.route('/')
def index():
    """Serve the main page, which will prompt for a room."""
    return render_template('index.html', room_id=None)


def initialize_room(room_id):
    """Initializes a room's data structure if it doesn't exist."""
    if room_id not in rooms:
        rooms[room_id] = {
            'users': [],
            'queue': [],  # ## NEW FEATURE: Changed from 'current_video' to 'queue'
            'current_video_index': -1,
            'state': 'PAUSED',
            'time': 0
        }
        logging.info(f"Initialized new room: '{room_id}'")


@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']

    initialize_room(room)  # Make sure room exists

    join_room(room)
    rooms[room]['users'].append(username)

    logging.info(f"'{username}' has joined room '{room}'")

    emit('user_list_update', {'users': rooms[room]['users']}, to=room)

    # ## NEW FEATURE: Sync the new user with the current state, including the full queue
    current_video_info = None
    if 0 <= rooms[room]['current_video_index'] < len(rooms[room]['queue']):
        current_video_info = rooms[room]['queue'][rooms[room]['current_video_index']]

    emit('sync_state', {
        'queue': rooms[room]['queue'],
        'current_video_index': rooms[room]['current_video_index'],
        'state': rooms[room]['state'],
        'time': rooms[room]['time']
    })


# ## NEW FEATURE: Event to add a video to the queue
@socketio.on('add_to_queue')
def on_add_to_queue(data):
    room = data['room']
    video_id = data.get('video_id')
    video_title = data.get('video_title', 'Untitled Video')  # Get title for the UI

    if room in rooms and video_id:
        video_info = {'id': video_id, 'title': video_title}
        rooms[room]['queue'].append(video_info)
        logging.info(f"Added video '{video_title}' to queue in room '{room}'")

        # Broadcast the updated queue to everyone
        emit('queue_update', {'queue': rooms[room]['queue']}, to=room)

        # If this is the first video, auto-play it
        if rooms[room]['current_video_index'] == -1:
            play_video_at_index(room, 0)


# ## NEW FEATURE: Event to play a specific video from the queue
@socketio.on('play_specific_video')
def on_play_specific_video(data):
    room = data['room']
    index = data.get('index')
    play_video_at_index(room, index)


def play_video_at_index(room, index):
    """Helper function to start playing a video at a specific queue index."""
    if room in rooms and 0 <= index < len(rooms[room]['queue']):
        rooms[room]['current_video_index'] = index
        rooms[room]['state'] = 'PLAYING'
        rooms[room]['time'] = 0

        video_info = rooms[room]['queue'][index]
        logging.info(f"Room '{room}' is now playing video at index {index}: {video_info['id']}")

        emit('state_change', {
            'event': 'load_video',
            'video_id': video_info['id'],
            'current_video_index': index,
            'time': 0,
            'state': 'PLAYING'
        }, to=room)


@socketio.on('player_event')
def on_player_event(data):
    room = data.get('room')
    if not room or room not in rooms:
        return

    event_type = data['event']

    # Update server's state first
    if event_type == 'play':
        rooms[room]['state'] = 'PLAYING'
        rooms[room]['time'] = data.get('time', 0)
    elif event_type == 'pause':
        rooms[room]['state'] = 'PAUSED'
        rooms[room]['time'] = data.get('time', 0)
    elif event_type == 'seek':
        rooms[room]['time'] = data.get('time', 0)
    elif event_type == 'video_ended':  # ## NEW FEATURE: Handle end of video to play next
        current_index = rooms[room]['current_video_index']
        next_index = current_index + 1
        if 0 <= next_index < len(rooms[room]['queue']):
            logging.info(f"Video ended in room '{room}', playing next.")
            play_video_at_index(room, next_index)
        else:
            logging.info(f"Queue ended in room '{room}'.")
            # Optionally, you can set the state to PAUSED or do something else
            rooms[room]['state'] = 'PAUSED'

    # Broadcast the event to other clients
    if event_type != 'video_ended':  # Don't need to re-broadcast the end event
        emit('state_change', data, to=room, include_self=False)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)