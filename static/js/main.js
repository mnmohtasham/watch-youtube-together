/* static/js/main.js */

// --- Globals ---
let player, currentRoom = '', currentUsername = '', isReceivingEvent = false;

// --- DOM Elements ---
const joinContainer = document.getElementById('join-container');
const mainContent = document.getElementById('main-content');
const landingPageContent = document.getElementById('landing-page-content'); // SEO Change
const joinBtn = document.getElementById('join-btn');
const addToQueueBtn = document.getElementById('add-to-queue-btn');
const roomNameEl = document.getElementById('room-name');
const userListEl = document.getElementById('user-list');
const shareLinkEl = document.getElementById('share-link');
const videoQueueEl = document.getElementById('video-queue');

// --- Socket.IO Connection ---
const socket = io();

document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    const parts = path.split('/');
    
    if (parts.length === 3 && parts[1] === 'room' && parts[2]) {
        const roomNameFromUrl = parts[2];
        document.getElementById('room').value = roomNameFromUrl;
        document.getElementById('room').disabled = true;
    }
});

joinBtn.addEventListener('click', () => {
    currentUsername = document.getElementById('username').value.trim();
    let roomInput = document.getElementById('room').value.trim();

    if (!currentUsername) {
        alert('Please enter a username.');
        return;
    }
    
    currentRoom = roomInput || `room-${Math.random().toString(36).substr(2, 5)}`;
    
    if (!roomInput) {
        window.history.pushState({}, '', `/room/${currentRoom}`);
    }

    socket.emit('join', { username: currentUsername, room: currentRoom });
    
    // --- UI Change ---
    joinContainer.style.display = 'none';
    landingPageContent.style.display = 'none'; // SEO Change: Hide landing content after joining a room
    mainContent.style.display = 'grid'; 
    roomNameEl.textContent = currentRoom;

    const shareableLink = window.location.origin + `/room/${currentRoom}`;
    shareLinkEl.textContent = shareableLink;
    shareLinkEl.style.display = 'block';
});

addToQueueBtn.addEventListener('click', () => {
    const videoUrl = document.getElementById('video-url').value;
    const videoId = extractVideoID(videoUrl);
    if (videoId) {
        socket.emit('add_to_queue', {
            room: currentRoom,
            video_id: videoId,
            video_title: `Video: ${videoId}` // Placeholder title
        });
        document.getElementById('video-url').value = '';
    } else {
        alert('Invalid YouTube URL');
    }
});

shareLinkEl.addEventListener('click', () => {
    navigator.clipboard.writeText(shareLinkEl.textContent).then(() => {
        alert('Room link copied to clipboard!');
    }, (err) => {
        console.error('Could not copy text: ', err);
    });
});

socket.on('queue_update', (data) => {
    renderQueue(data.queue);
});

socket.on('user_list_update', (data) => {
    userListEl.innerHTML = '';
    data.users.forEach(user => {
        const li = document.createElement('li');
        li.textContent = user;
        userListEl.appendChild(li);
    });
});

socket.on('sync_state', (data) => {
    console.log('Syncing state from server:', data);
    isReceivingEvent = true;
    renderQueue(data.queue, data.current_video_index);
    if (player && data.current_video_index > -1) {
        const video = data.queue[data.current_video_index];
        player.loadVideoById(video.id);
        setTimeout(() => {
            player.seekTo(data.time, true);
            if (data.state === 'PLAYING') {
                player.playVideo();
            } else {
                player.pauseVideo();
            }
            setTimeout(() => { isReceivingEvent = false; }, 1200);
        }, 200);
    } else {
        isReceivingEvent = false;
    }
});

socket.on('state_change', (data) => {
    if (!player) return;
    console.log('Received state change:', data);
    isReceivingEvent = true;
    if(data.current_video_index !== undefined) {
        updateNowPlaying(data.current_video_index);
    }
    switch (data.event) {
        case 'load_video':
            player.loadVideoById(data.video_id, data.time);
            if (data.state === 'PLAYING') player.playVideo();
            break;
        case 'play':
            player.seekTo(data.time, true);
            player.playVideo();
            break;
        case 'pause':
            player.pauseVideo();
            player.seekTo(data.time, true);
            break;
        case 'seek':
            player.seekTo(data.time, true);
            break;
    }
    setTimeout(() => { isReceivingEvent = false; }, 500);
});

function onYouTubeIframeAPIReady() {
    player = new YT.Player('player', {
        height: '100%', width: '100%',
        events: { 'onReady': onPlayerReady, 'onStateChange': onPlayerStateChange },
        playerVars: { 'mute': 1 }
    });
}

function onPlayerReady(event) { console.log('Player is ready.'); }

function onPlayerStateChange(event) {
    if (isReceivingEvent) return;
    const currentTime = player.getCurrentTime();
    let state;
    switch (event.data) {
        case YT.PlayerState.PLAYING: state = 'play'; break;
        case YT.PlayerState.PAUSED: state = 'pause'; break;
        case YT.PlayerState.ENDED: state = 'video_ended'; break;
        case YT.PlayerState.BUFFERING: state = 'seek'; break;
        default: return;
    }
    console.log('Sending player event:', state);
    socket.emit('player_event', { room: currentRoom, event: state, time: currentTime });
}

function extractVideoID(url) {
    const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/;
    return url.match(regex)?.[1] || null;
}

function renderQueue(queue, nowPlayingIndex = -1) {
    videoQueueEl.innerHTML = '';
    queue.forEach((video, index) => {
        const li = document.createElement('li');
        li.dataset.index = index;
        li.innerHTML = `<span class="video-title">${video.title}</span><small>Play</small>`;
        if (index === nowPlayingIndex) li.classList.add('now-playing');
        li.addEventListener('click', () => {
            socket.emit('play_specific_video', { room: currentRoom, index: index });
        });
        videoQueueEl.appendChild(li);
    });
}

function updateNowPlaying(index) {
    document.querySelectorAll('#video-queue li').forEach(li => li.classList.remove('now-playing'));
    const currentItem = document.querySelector(`#video-queue li[data-index="${index}"]`);
    if (currentItem) currentItem.classList.add('now-playing');
}

var tag = document.createElement('script');
tag.src = "https://www.youtube.com/iframe_api";
var firstScriptTag = document.getElementsByTagName('script')[0];
firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);