// static/js/app.js

// --- YT Player Setup ---
let player;
window.onYouTubeIframeAPIReady = function() {
    player = new YT.Player('player', {
        height: '390',
        width: '640',
        videoId: '', // Initially empty
        playerVars: {
            'playsinline': 1,
            'autoplay': 0,
            'controls': 1
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange
        }
    });
};

// --- Socket.IO Connection ---
const socket = io();

// --- Global State ---
// FIX: Rename 'isSeeking' to 'isSyncing' for clarity. It's for blocking events
// that come from the server, not just for seeking.
let isSyncing = false;
let localState = {
    current_video_index: -1,
    state: 'PAUSED',
    time: 0,
};

// --- DOM Elements ---
const mainContent = document.getElementById('main-content');
const addVideoForm = document.getElementById('add-video-form');
const videoUrlInput = document.getElementById('video-url-input');
const userList = document.getElementById('user-list');
const videoQueue = document.getElementById('video-queue');

// --- Socket Event Listeners ---
socket.on('connect', () => {
    console.log('Connected to server!');
    mainContent.style.display = 'grid';
    socket.emit('join', { room: ROOM_ID });
});

socket.on('disconnect', () => {
    console.log('Disconnected from server.');
    mainContent.style.display = 'none';
});

socket.on('sync_state', (data) => {
    console.log('Syncing state:', data);
    isSyncing = true; // Prevent sending events while syncing initial state
    localState = { ...localState, ...data };
    updateQueueUI(data.queue, data.current_video_index);
    if (data.current_video_index !== -1 && data.queue.length > 0) {
        const videoId = data.queue[data.current_video_index].id;
        player.loadVideoById(videoId, data.time);
        if (data.state === 'PLAYING') {
            player.playVideo();
        } else {
            player.pauseVideo();
        }
    }
    setTimeout(() => { isSyncing = false; }, 500);
});

socket.on('state_change', (data) => {
    console.log('Received state change from server:', data);
    isSyncing = true; // Set the flag to true because we are processing a server event
    localState.state = data.state;
    localState.time = data.time;

    switch (data.event) {
        case 'load_video':
            player.loadVideoById(data.video_id, data.time);
            updateQueueUI(null, data.current_video_index);
            if (data.state === 'PLAYING') player.playVideo();
            break;
        case 'play':
            player.playVideo();
            break;
        case 'pause':
            player.pauseVideo();
            break;
        
        // *** THE CORE FIX IS HERE ***
        // We now use the 'state' property sent from the server to decide
        // whether to resume playing after the seek is complete.
        case 'seek':
            player.seekTo(data.time, true);
            if (data.state === 'PLAYING') {
                player.playVideo();
            }
            break;
    }
    // Release the lock after a short delay
    setTimeout(() => { isSyncing = false; }, 500);
});

socket.on('queue_update', (data) => {
    console.log('Queue updated:', data.queue);
    updateQueueUI(data.queue, localState.current_video_index);
});

socket.on('user_list_update', (data) => {
    console.log('User list updated:', data.users);
    updateUserListUI(data.users);
});

// --- Player Event Handlers ---
function onPlayerReady(event) {
    console.log('YouTube Player is ready.');
}

function onPlayerStateChange(event) {
    // If we are processing an update from the server, do nothing.
    if (isSyncing) return;

    switch (event.data) {
        case YT.PlayerState.PLAYING:
            socket.emit('player_event', { room: ROOM_ID, event: 'play', time: player.getCurrentTime() });
            break;
        case YT.PlayerState.PAUSED:
            // This event will still fire when the user seeks, but our seek detector below
            // will fire a more specific 'seek' event immediately after.
            socket.emit('player_event', { room: ROOM_ID, event: 'pause', time: player.getCurrentTime() });
            break;
        case YT.PlayerState.ENDED:
            socket.emit('player_event', { room: ROOM_ID, event: 'video_ended' });
            break;
    }
}

// --- Robust Seek Detection ---
// This interval constantly checks for large time jumps.
setInterval(() => {
    // Don't run if the player isn't ready or if we're processing a server update.
    if (isSyncing || !player || typeof player.getCurrentTime !== 'function') {
        return;
    }

    const currentTime = player.getCurrentTime();
    
    // *** THE SECOND FIX IS HERE ***
    // This now detects a seek regardless of whether the video is playing or paused.
    // A "seek" is defined as a time jump of more than 1.5 seconds between checks.
    if (Math.abs(currentTime - localState.time) > 1.5) {
         console.log(`Seek detected via time jump. Player time: ${currentTime}`);
         socket.emit('player_event', { room: ROOM_ID, event: 'seek', time: currentTime });
         localState.time = currentTime; // Immediately update local time to prevent re-firing
         return; // Don't update time again below
    }

    // Always keep local time updated for the next check.
    localState.time = currentTime;

}, 250); // Check 4 times a second for better responsiveness.


// --- UI Update Functions (No Changes Needed Here) ---
function updateQueueUI(queue, currentIndex) {
    if (queue) {
        videoQueue.innerHTML = '';
        queue.forEach((video, index) => {
            const li = document.createElement('li');
            li.innerHTML = `<span class="video-title">${video.title || 'Untitled Video'}</span>`;
            li.dataset.index = index;
            if (index === currentIndex) {
                li.classList.add('now-playing');
            }
            li.onclick = () => {
                socket.emit('play_specific_video', { room: ROOM_ID, index: index });
            };
            videoQueue.appendChild(li);
        });
    } else {
        document.querySelectorAll('#video-queue li').forEach(li => {
            li.classList.remove('now-playing');
            if (parseInt(li.dataset.index, 10) === currentIndex) {
                li.classList.add('now-playing');
            }
        });
    }
    localState.current_video_index = currentIndex;
}

function updateUserListUI(users) {
    userList.innerHTML = '';
    users.forEach(user => {
        const li = document.createElement('li');
        li.textContent = user;
        userList.appendChild(li);
    });
}

// --- Form Submission (No Changes Needed Here) ---
addVideoForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = videoUrlInput.value.trim();
    if (url) {
        const videoId = extractYouTubeID(url);
        if (videoId) {
            socket.emit('add_to_queue', {
                room: ROOM_ID,
                video_id: videoId,
                video_title: `Video: ${videoId}`
            });
            videoUrlInput.value = '';
        } else {
            alert('Could not extract a valid YouTube Video ID from the URL.');
        }
    }
});

function extractYouTubeID(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}