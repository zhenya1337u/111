from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import time
import random

app = Flask(__name__, static_folder=None)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading') # Using threading async_mode

# Game Constants
COURT_WIDTH = 800
COURT_HEIGHT = 400
BALL_RADIUS = 7
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
INITIAL_BALL_SPEED_X = 4
INITIAL_BALL_SPEED_Y = 4

# Global game state
gameState = {
    'ball': {
        'x': COURT_WIDTH / 2,
        'y': COURT_HEIGHT / 2,
        'speedX': INITIAL_BALL_SPEED_X * (random.choice([-1, 1])),
        'speedY': INITIAL_BALL_SPEED_Y * (random.choice([-1, 1]))
    },
    'paddles': {},  # Will store {sid: y_pos}
    'scores': {
        'player1': 0,
        'player2': 0
    },
    'game_on': False, # Flag to indicate if the game loop should be processing
    'player_roles': {} # {sid: 'player1' or 'player2'}
}

# Connected players management
# players object stores sid: {'role': 'player1'/'player2'}
players = {}
game_loop_task = None
GAME_UPDATE_INTERVAL = 1/60 # approx 60 FPS

def reset_ball(new_direction_x=None):
    """Resets the ball to the center with a random or specified direction."""
    gameState['ball']['x'] = COURT_WIDTH / 2
    gameState['ball']['y'] = COURT_HEIGHT / 2
    if new_direction_x is not None:
        gameState['ball']['speedX'] = INITIAL_BALL_SPEED_X * new_direction_x
    else:
        gameState['ball']['speedX'] = INITIAL_BALL_SPEED_X * (random.choice([-1, 1]))
    gameState['ball']['speedY'] = INITIAL_BALL_SPEED_Y * (random.choice([-1, 1]))

def server_game_loop():
    """Main game loop running on the server."""
    while True:
        if gameState['game_on'] and len(players) >= 1: # Require at least one player to keep running, 2 for active play
            # Update Ball Position
            ball = gameState['ball']
            ball['x'] += ball['speedX']
            ball['y'] += ball['speedY']

            # Collision Detection: Top/Bottom Walls
            if ball['y'] - BALL_RADIUS < 0:
                ball['y'] = BALL_RADIUS
                ball['speedY'] *= -1
            elif ball['y'] + BALL_RADIUS > COURT_HEIGHT:
                ball['y'] = COURT_HEIGHT - BALL_RADIUS
                ball['speedY'] *= -1

            # Collision Detection: Paddles
            player1_sid, player2_sid = None, None
            for sid, role_info in players.items():
                if role_info['role'] == 'player1': player1_sid = sid
                if role_info['role'] == 'player2': player2_sid = sid
            
            # Left Paddle (Player 1)
            if player1_sid and player1_sid in gameState['paddles']:
                paddle1_y = gameState['paddles'][player1_sid]
                if ball['x'] - BALL_RADIUS < PADDLE_WIDTH + 10 and \
                   ball['y'] > paddle1_y and ball['y'] < paddle1_y + PADDLE_HEIGHT and \
                   ball['speedX'] < 0: # Check if ball is moving towards paddle
                    ball['x'] = PADDLE_WIDTH + 10 + BALL_RADIUS # Place ball outside paddle
                    ball['speedX'] *= -1
                    # Optional: Add some randomness or angle based on hit
                    # ball['speedY'] += (ball['y'] - (paddle1_y + PADDLE_HEIGHT / 2)) * 0.1


            # Right Paddle (Player 2)
            if player2_sid and player2_sid in gameState['paddles']:
                paddle2_y = gameState['paddles'][player2_sid]
                if ball['x'] + BALL_RADIUS > COURT_WIDTH - PADDLE_WIDTH - 10 and \
                   ball['y'] > paddle2_y and ball['y'] < paddle2_y + PADDLE_HEIGHT and \
                   ball['speedX'] > 0: # Check if ball is moving towards paddle
                    ball['x'] = COURT_WIDTH - PADDLE_WIDTH - 10 - BALL_RADIUS # Place ball outside paddle
                    ball['speedX'] *= -1
                    # Optional: Add some randomness or angle based on hit
                    # ball['speedY'] += (ball['y'] - (paddle2_y + PADDLE_HEIGHT / 2)) * 0.1
            
            # Scoring
            if ball['x'] - BALL_RADIUS < 0: # Ball goes past left paddle
                gameState['scores']['player2'] += 1
                print(f"Player 2 scores! Score: P1 {gameState['scores']['player1']} - P2 {gameState['scores']['player2']}")
                reset_ball(new_direction_x=1) # Ball serves towards Player 2
                socketio.emit('score_update', gameState['scores'])
            elif ball['x'] + BALL_RADIUS > COURT_WIDTH: # Ball goes past right paddle
                gameState['scores']['player1'] += 1
                print(f"Player 1 scores! Score: P1 {gameState['scores']['player1']} - P2 {gameState['scores']['player2']}")
                reset_ball(new_direction_x=-1) # Ball serves towards Player 1
                socketio.emit('score_update', gameState['scores'])

            # Broadcast Game State
            socketio.emit('game_update', gameState)
        
        socketio.sleep(GAME_UPDATE_INTERVAL)


# Serve static files
STATIC_FOLDER = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if ".." in filename or filename.startswith("/"):
        return "Invalid path", 400
    return send_from_directory(STATIC_FOLDER, filename)

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    global game_loop_task
    sid = request.sid
    print(f'Client connected: {sid}')

    assigned_role = None
    if 'player1' not in [p['role'] for p in players.values()]:
        assigned_role = 'player1'
        players[sid] = {'role': 'player1'}
        gameState['paddles'][sid] = COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2 # Initial Y
    elif 'player2' not in [p['role'] for p in players.values()]:
        assigned_role = 'player2'
        players[sid] = {'role': 'player2'}
        gameState['paddles'][sid] = COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2 # Initial Y
    else:
        # Spectator or reject
        emit('game_full', {'message': 'Game is full. You are a spectator.'}, room=sid)
        print(f"Connection {sid} is a spectator or rejected.")
        return # Don't proceed further for spectators for now

    gameState['player_roles'][sid] = assigned_role
    emit('player_assignment', {'role': assigned_role, 'sid': sid}, room=sid)
    emit('game_update', gameState, room=sid) # Send initial state to the new player
    print(f"Player {assigned_role} ({sid}) connected. Total players: {len(players)}")
    print("Current players:", players)
    print("Current paddles state:", gameState['paddles'])


    if len(players) == 1 and game_loop_task is None: # Start loop if it's the first player and loop not running
        # gameState['game_on'] = True # Wait for start_game signal
        # print("Game loop task starting because first player joined.")
        # game_loop_task = socketio.start_background_task(target=server_game_loop)
        pass # Game loop will be started by 'start_game' event

    if len(players) == 2:
         emit('message', {'text': 'Two players connected. Ready to start!'}, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f'Client disconnected: {sid}')
    if sid in players:
        assigned_role = players[sid]['role']
        del players[sid]
        if sid in gameState['paddles']:
            del gameState['paddles'][sid]
        if sid in gameState['player_roles']:
            del gameState['player_roles'][sid]
        
        print(f"Player {assigned_role} ({sid}) disconnected. Remaining players: {len(players)}")
        # Reset scores if a player leaves? Or just pause?
        # gameState['scores'] = {'player1': 0, 'player2': 0}
        # socketio.emit('score_update', gameState['scores'])
        
        if len(players) < 2:
            gameState['game_on'] = False # Stop game if not enough players
            print("Game paused due to player disconnect.")
            # Consider what happens to the game_loop_task; it keeps running but game_on is false.
        
        emit('player_disconnected', {'role': assigned_role, 'sid': sid}, broadcast=True)
    else:
        print(f"Spectator or unassigned client {sid} disconnected.")


@socketio.on('paddle_move')
def handle_paddle_move(data):
    sid = request.sid
    if sid in players and sid in gameState['paddles']:
        new_y = data.get('y')
        if isinstance(new_y, (int, float)):
            # Constrain paddle movement
            if new_y < 0:
                new_y = 0
            if new_y + PADDLE_HEIGHT > COURT_HEIGHT:
                new_y = COURT_HEIGHT - PADDLE_HEIGHT
            
            gameState['paddles'][sid] = new_y
            # No need to emit game_update here, loop does it
        else:
            print(f"Invalid paddle_move data from {sid}: {data}")
    else:
        print(f"paddle_move from unknown or unassigned player {sid}")


@socketio.on('start_game')
def handle_start_game(data): # data could contain who is starting, if needed
    global game_loop_task
    sid = request.sid
    if sid not in players:
        print(f"Unauthorized start_game attempt by {sid}")
        return

    if len(players) >= 1: # Allow starting with 1 player for testing, or change to >= 2
        print(f"Start game event received from {sid}. Current players: {len(players)}")
        gameState['scores'] = {'player1': 0, 'player2': 0}
        reset_ball()
        gameState['game_on'] = True
        socketio.emit('score_update', gameState['scores']) # Inform clients of score reset
        socketio.emit('game_started', {'started_by': sid}) # Inform clients game is on
        
        if game_loop_task is None:
            print("Starting game loop background task.")
            game_loop_task = socketio.start_background_task(target=server_game_loop)
        else:
            print("Game loop task already running.")
        print("Game state set to ON.")
    else:
        emit('message', {'text': 'Not enough players to start the game.'}, room=sid)
        print("Not enough players to start.")

@socketio.on('reset_game') # Similar to start_game but might be callable mid-game
def handle_reset_game(data):
    sid = request.sid
    if sid not in players: # Only allow players to reset
        print(f"Unauthorized reset_game attempt by {sid}")
        return

    print(f"Reset game event received from {sid}")
    gameState['scores'] = {'player1': 0, 'player2': 0}
    reset_ball()
    socketio.emit('score_update', gameState['scores'])
    # game_on remains as is, if game was on, it continues with reset state.
    # if game was off, it remains off until start_game.
    socketio.emit('game_update', gameState) # Send full update after reset
    print("Game state reset.")

@socketio.on('client_message') # For testing connection
def handle_client_message(data):
    print(f"Received message from client ({request.sid}): {data}")
    emit('server_response', {'data': f'Server received your message: {data.get("message")}'}, room=request.sid)


if __name__ == '__main__':
    print(f"Starting server, serving files from: {STATIC_FOLDER}")
    # Ensure game_loop_task is not started here if you want 'start_game' to control it
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
    # use_reloader=False is important for background tasks
    # allow_unsafe_werkzeug=True for Flask dev server with SocketIO
```
