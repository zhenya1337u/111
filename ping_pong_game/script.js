// 1. Get references to DOM elements
const canvas = document.getElementById('gameCanvas');
const player1ScoreDisplay = document.getElementById('player1Score');
const player2ScoreDisplay = document.getElementById('player2Score');
const startButton = document.getElementById('startButton');
const resetButton = document.getElementById('resetButton');

// 2. Set up the canvas
const ctx = canvas.getContext('2d');
const COURT_WIDTH = 800;
const COURT_HEIGHT = 400;
canvas.width = COURT_WIDTH;
canvas.height = COURT_HEIGHT;

// 3. Define game objects (variables) - These will be largely controlled by server state
// Paddles
const PADDLE_WIDTH = 10;
const PADDLE_HEIGHT = 100;
// const PADDLE_SPEED = 5; // Client-side paddle speed for local prediction (optional)

const leftPaddle = {
    x: 10, // Initial position, server will confirm/update
    y: COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2,
    width: PADDLE_WIDTH,
    height: PADDLE_HEIGHT,
};

const rightPaddle = {
    x: COURT_WIDTH - PADDLE_WIDTH - 10, // Initial position, server will confirm/update
    y: COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2,
    width: PADDLE_WIDTH,
    height: PADDLE_HEIGHT,
};

// Ball
const BALL_RADIUS = 7;
const ball = {
    x: COURT_WIDTH / 2, // Initial position, server will confirm/update
    y: COURT_HEIGHT / 2,
    radius: BALL_RADIUS,
    // speedX and speedY are now server-controlled
};

// Scores
let player1Score = 0;
let player2Score = 0;

// Player identification
let myPlayerRole = null; // 'player1' or 'player2'
let myPlayerSid = null;  // Current client's socket ID

// 4. Implement drawing functions
function drawCourt() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, COURT_WIDTH, COURT_HEIGHT);
    ctx.fillStyle = '#FFF';
    ctx.fillRect(COURT_WIDTH / 2 - 1, 0, 2, COURT_HEIGHT);
}

function drawPaddle(paddle) {
    ctx.fillStyle = '#FFF';
    ctx.fillRect(paddle.x, paddle.y, paddle.width, paddle.height);
}

function drawBall(_ball) { // Renamed to avoid conflict with global ball
    ctx.fillStyle = '#FFF';
    ctx.beginPath();
    ctx.arc(_ball.x, _ball.y, _ball.radius, 0, Math.PI * 2);
    ctx.fill();
}

function updateScoreDisplay() {
    player1ScoreDisplay.textContent = player1Score;
    player2ScoreDisplay.textContent = player2Score;
}

// 5. Main Rendering Loop (driven by server updates)
function gameLoop() {
    // Clearing the canvas is done by drawCourt filling the background
    drawCourt();
    drawPaddle(leftPaddle);
    drawPaddle(rightPaddle);
    drawBall(ball); // Use the global ball object, updated by server
    requestAnimationFrame(gameLoop);
}

// 6. Initial rendering (optional, server will send initial state)
updateScoreDisplay();
drawCourt();
drawPaddle(leftPaddle);
drawPaddle(rightPaddle);
drawBall(ball);
console.log("script.js loaded. Waiting for server connection and player assignment.");

// 7. WebSocket Integration
const socket = io();

socket.on('connect', () => {
    myPlayerSid = socket.id; // Store SID on connect
    console.log('Connected to server! My SID:', myPlayerSid);
    socket.emit('client_message', { message: 'Hello from client!' });
});

socket.on('disconnect', () => {
    console.log('Disconnected from server.');
    myPlayerRole = null; // Reset role on disconnect
    // Optionally, display a message or handle UI changes for disconnection
});

socket.on('player_assignment', (data) => {
    myPlayerRole = data.role;
    console.log(`I am assigned as: ${myPlayerRole} (SID: ${data.sid})`);
    // If this client is data.sid, then it's myPlayerRole.
    // This also helps if server needs to re-assign or confirm roles.
    if (data.sid === myPlayerSid) {
        console.log(`Role confirmed: ${myPlayerRole}`);
    }
    // Start the rendering loop once player is assigned, if not already running
    // requestAnimationFrame(gameLoop); // Game loop started below unconditionally for now
});

socket.on('game_update', (serverGameState) => {
    // console.log('Received game_update:', serverGameState);

    // Update ball
    ball.x = serverGameState.ball.x;
    ball.y = serverGameState.ball.y;

    // Update paddles based on player_roles and paddles data from server
    // serverGameState.paddles is { sid1: y_pos, sid2: y_pos }
    // serverGameState.player_roles is { sid1: 'player1', sid2: 'player2' }
    for (const sid in serverGameState.player_roles) {
        const role = serverGameState.player_roles[sid];
        const paddleY = serverGameState.paddles[sid];
        if (paddleY === undefined) continue; // Skip if paddle data for a SID is missing

        if (role === 'player1') {
            leftPaddle.y = paddleY;
        } else if (role === 'player2') {
            rightPaddle.y = paddleY;
        }
    }
    
    // Update scores
    if (serverGameState.scores) {
        player1Score = serverGameState.scores.player1;
        player2Score = serverGameState.scores.player2;
        updateScoreDisplay();
    }
});

socket.on('score_update', (scores) => {
    console.log('Received score_update:', scores);
    player1Score = scores.player1;
    player2Score = scores.player2;
    updateScoreDisplay();
});

socket.on('game_started', (data) => {
    console.log('Game started by:', data.started_by);
    // Potentially enable UI elements or show messages
});

socket.on('player_disconnected', (data) => {
    console.log(`Player ${data.role} (SID: ${data.sid}) disconnected.`);
    // Update UI or game state if needed
});

socket.on('game_full', (data) => {
    console.warn(data.message);
    // Display this message to the user
});

socket.on('message', (data) => { // General messages from server
    console.log('Server message:', data.text);
});


// 8. Paddle Movement (Local Player Control)
canvas.addEventListener('mousemove', (event) => {
    if (!myPlayerRole) return; // Don't allow movement if no role assigned

    const rect = canvas.getBoundingClientRect();
    let newY = event.clientY - rect.top - PADDLE_HEIGHT / 2; // Center paddle on mouse

    // Constrain paddle to canvas
    if (newY < 0) newY = 0;
    if (newY + PADDLE_HEIGHT > COURT_HEIGHT) newY = COURT_HEIGHT - PADDLE_HEIGHT;

    let paddleToMove = null;
    if (myPlayerRole === 'player1') {
        paddleToMove = leftPaddle;
    } else if (myPlayerRole === 'player2') {
        paddleToMove = rightPaddle;
    }

    if (paddleToMove) {
        paddleToMove.y = newY; // Local update for responsiveness (client-side prediction)
        socket.emit('paddle_move', { y: newY });
    }
});

// 9. UI Button Event Listeners
startButton.addEventListener('click', () => {
    console.log('Start Game button clicked');
    socket.emit('start_game', {});
});

resetButton.addEventListener('click', () => {
    console.log('Reset Game button clicked');
    socket.emit('reset_game', {});
});

// Start the rendering loop
requestAnimationFrame(gameLoop);
console.log("Rendering loop started.");
