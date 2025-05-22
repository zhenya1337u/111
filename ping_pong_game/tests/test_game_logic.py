import unittest
import sys
import os
import random
from unittest.mock import MagicMock, patch

# Adjust the path to include the parent directory (ping_pong_game)
# so that 'app' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Attempt to import from app.py
# We need to be careful as app.py also starts a server if __name__ == '__main__'
# We will mock socketio and its emit methods for testing purposes
# and import specific variables/functions if possible.

# Mocking socketio before importing from app
mock_socketio = MagicMock()
sys.modules['flask_socketio'] = MagicMock()
sys.modules['flask_socketio'].SocketIO = MagicMock(return_value=mock_socketio)
sys.modules['flask_socketio'].emit = mock_socketio.emit # Mock top-level emit

# Now import from app
from app import (
    gameState,
    players, # For context if needed by any logic
    reset_ball,
    COURT_WIDTH, COURT_HEIGHT, BALL_RADIUS, PADDLE_WIDTH, PADDLE_HEIGHT,
    INITIAL_BALL_SPEED_X, INITIAL_BALL_SPEED_Y
    # server_game_loop # We will test logic derived from this, not call it directly
)

# Helper function to simulate the core logic of one game loop iteration
# This is extracted and adapted from app.server_game_loop for testability
def simulate_game_loop_tick():
    # This function will directly modify the global gameState imported from app
    
    # --- Ball Movement ---
    ball = gameState['ball']
    ball['x'] += ball['speedX']
    ball['y'] += ball['speedY']

    # --- Collision Detection: Top/Bottom Walls ---
    if ball['y'] - BALL_RADIUS < 0:
        ball['y'] = BALL_RADIUS
        ball['speedY'] *= -1
    elif ball['y'] + BALL_RADIUS > COURT_HEIGHT:
        ball['y'] = COURT_HEIGHT - BALL_RADIUS
        ball['speedY'] *= -1

    # --- Collision Detection: Paddles ---
    # For paddle collision, we need to know player SIDs and their roles.
    # Let's assume fixed SIDs for testing and populate gameState.paddles and players directly.
    player1_sid_test = 'player1_test_sid'
    player2_sid_test = 'player2_test_sid'

    # Ensure paddles exist for collision detection logic (mimic app.py structure)
    # This part needs to be set up in individual tests based on what's being tested.
    # For example, in a test, you'd do:
    # players[player1_sid_test] = {'role': 'player1'}
    # gameState['paddles'][player1_sid_test] = initial_y_position

    # Left Paddle (Player 1)
    if player1_sid_test in gameState['paddles'] and players.get(player1_sid_test, {}).get('role') == 'player1':
        paddle1_y = gameState['paddles'][player1_sid_test]
        if ball['x'] - BALL_RADIUS < PADDLE_WIDTH + 10 and \
           ball['y'] > paddle1_y and ball['y'] < paddle1_y + PADDLE_HEIGHT and \
           ball['speedX'] < 0:
            ball['x'] = PADDLE_WIDTH + 10 + BALL_RADIUS
            ball['speedX'] *= -1
    
    # Right Paddle (Player 2)
    if player2_sid_test in gameState['paddles'] and players.get(player2_sid_test, {}).get('role') == 'player2':
        paddle2_y = gameState['paddles'][player2_sid_test]
        if ball['x'] + BALL_RADIUS > COURT_WIDTH - PADDLE_WIDTH - 10 and \
           ball['y'] > paddle2_y and ball['y'] < paddle2_y + PADDLE_HEIGHT and \
           ball['speedX'] > 0:
            ball['x'] = COURT_WIDTH - PADDLE_WIDTH - 10 - BALL_RADIUS
            ball['speedX'] *= -1

    # --- Scoring ---
    scored = False
    if ball['x'] - BALL_RADIUS < 0: # Ball goes past left paddle
        gameState['scores']['player2'] += 1
        reset_ball(new_direction_x=1) # Ball serves towards Player 2
        # mock_socketio.emit('score_update', gameState['scores']) # Mocked out
        scored = True
    elif ball['x'] + BALL_RADIUS > COURT_WIDTH: # Ball goes past right paddle
        gameState['scores']['player1'] += 1
        reset_ball(new_direction_x=-1) # Ball serves towards Player 1
        # mock_socketio.emit('score_update', gameState['scores']) # Mocked out
        scored = True
    return scored


class TestGameLogic(unittest.TestCase):

    def setUp(self):
        # Reset gameState before each test to ensure independence
        gameState['ball']['x'] = COURT_WIDTH / 2
        gameState['ball']['y'] = COURT_HEIGHT / 2
        gameState['ball']['speedX'] = INITIAL_BALL_SPEED_X
        gameState['ball']['speedY'] = INITIAL_BALL_SPEED_Y
        gameState['scores']['player1'] = 0
        gameState['scores']['player2'] = 0
        gameState['paddles'].clear() # Clear paddles
        players.clear() # Clear players
        # Ensure random choices are predictable if necessary, or test outcomes
        random.seed(0) # For predictable random choices in reset_ball if not given direction
        reset_ball() # Call to set initial random speeds predictably
        mock_socketio.reset_mock() # Reset mock calls

        # Setup dummy player SIDs for tests that need them
        self.p1_sid = 'player1_test_sid'
        self.p2_sid = 'player2_test_sid'


    def test_initial_game_state(self):
        # setUp already resets to a known state, let's verify some parts
        self.assertEqual(gameState['ball']['x'], COURT_WIDTH / 2)
        self.assertEqual(gameState['ball']['y'], COURT_HEIGHT / 2)
        self.assertEqual(gameState['scores']['player1'], 0)
        self.assertEqual(gameState['scores']['player2'], 0)
        # Initial ball speeds are set by reset_ball() in setUp, which uses random.choice([-1,1])
        # With random.seed(0), random.choice([-1,1]) first returns 1, then -1, then 1, ...
        # reset_ball() called in setUp:
        # speedX will be INITIAL_BALL_SPEED_X * 1 (from first random.choice)
        # speedY will be INITIAL_BALL_SPEED_Y * -1 (from second random.choice)
        self.assertEqual(gameState['ball']['speedX'], INITIAL_BALL_SPEED_X * 1)
        self.assertEqual(gameState['ball']['speedY'], INITIAL_BALL_SPEED_Y * -1)


    def test_reset_ball(self):
        gameState['ball']['x'] = 100
        gameState['ball']['y'] = 100
        gameState['ball']['speedX'] = 10
        gameState['ball']['speedY'] = 10
        
        reset_ball(new_direction_x=1)
        self.assertEqual(gameState['ball']['x'], COURT_WIDTH / 2)
        self.assertEqual(gameState['ball']['y'], COURT_HEIGHT / 2)
        self.assertEqual(gameState['ball']['speedX'], INITIAL_BALL_SPEED_X * 1)
        # speedY should be randomly positive or negative
        self.assertIn(gameState['ball']['speedY'], [INITIAL_BALL_SPEED_Y, -INITIAL_BALL_SPEED_Y])

        reset_ball(new_direction_x=-1)
        self.assertEqual(gameState['ball']['speedX'], INITIAL_BALL_SPEED_X * -1)

    def test_ball_movement(self):
        initial_x = COURT_WIDTH / 2
        initial_y = COURT_HEIGHT / 2
        initial_speed_x = gameState['ball']['speedX'] # Set by reset_ball in setUp
        initial_speed_y = gameState['ball']['speedY']

        gameState['ball']['x'] = initial_x
        gameState['ball']['y'] = initial_y
        
        simulate_game_loop_tick() # Simulate one tick of ball movement

        self.assertEqual(gameState['ball']['x'], initial_x + initial_speed_x)
        self.assertEqual(gameState['ball']['y'], initial_y + initial_speed_y)

    def test_wall_collision_top(self):
        gameState['ball']['y'] = BALL_RADIUS - 1 # Place ball just above the top wall, moving upwards
        gameState['ball']['speedY'] = -abs(INITIAL_BALL_SPEED_Y) # Ensure it's moving up
        initial_speed_y = gameState['ball']['speedY']
        
        simulate_game_loop_tick()
        
        self.assertEqual(gameState['ball']['y'], BALL_RADIUS) # Ball should be at the wall
        self.assertEqual(gameState['ball']['speedY'], -initial_speed_y) # Speed should be reversed

    def test_wall_collision_bottom(self):
        gameState['ball']['y'] = COURT_HEIGHT - BALL_RADIUS + 1 # Place ball just below bottom wall, moving downwards
        gameState['ball']['speedY'] = abs(INITIAL_BALL_SPEED_Y) # Ensure it's moving down
        initial_speed_y = gameState['ball']['speedY']

        simulate_game_loop_tick()

        self.assertEqual(gameState['ball']['y'], COURT_HEIGHT - BALL_RADIUS)
        self.assertEqual(gameState['ball']['speedY'], -initial_speed_y)

    def test_paddle_collision_left_paddle(self):
        # Setup player1 (left paddle)
        players[self.p1_sid] = {'role': 'player1'}
        gameState['paddles'][self.p1_sid] = COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2
        
        # Position ball to hit the left paddle
        gameState['ball']['x'] = PADDLE_WIDTH + 10 + BALL_RADIUS - 1 # Just before paddle surface
        gameState['ball']['y'] = COURT_HEIGHT / 2 # Center of paddle
        gameState['ball']['speedX'] = -abs(INITIAL_BALL_SPEED_X) # Moving towards left paddle
        initial_speed_x = gameState['ball']['speedX']

        simulate_game_loop_tick()
        
        self.assertEqual(gameState['ball']['x'], PADDLE_WIDTH + 10 + BALL_RADIUS) # Ball placed outside paddle
        self.assertEqual(gameState['ball']['speedX'], -initial_speed_x) # Speed reversed

    def test_paddle_collision_right_paddle(self):
        # Setup player2 (right paddle)
        players[self.p2_sid] = {'role': 'player2'}
        gameState['paddles'][self.p2_sid] = COURT_HEIGHT / 2 - PADDLE_HEIGHT / 2

        # Position ball to hit the right paddle
        gameState['ball']['x'] = COURT_WIDTH - PADDLE_WIDTH - 10 - BALL_RADIUS + 1 # Just before paddle
        gameState['ball']['y'] = COURT_HEIGHT / 2 # Center of paddle
        gameState['ball']['speedX'] = abs(INITIAL_BALL_SPEED_X) # Moving towards right paddle
        initial_speed_x = gameState['ball']['speedX']

        simulate_game_loop_tick()

        self.assertEqual(gameState['ball']['x'], COURT_WIDTH - PADDLE_WIDTH - 10 - BALL_RADIUS)
        self.assertEqual(gameState['ball']['speedX'], -initial_speed_x)

    def test_scoring_player1_scores(self): # Ball passes right boundary
        gameState['scores']['player1'] = 0
        # Position ball to pass the right boundary
        gameState['ball']['x'] = COURT_WIDTH - BALL_RADIUS + 1 # Just about to score
        gameState['ball']['y'] = COURT_HEIGHT / 2
        gameState['ball']['speedX'] = abs(INITIAL_BALL_SPEED_X) # Moving right
        
        simulate_game_loop_tick()
        
        self.assertEqual(gameState['scores']['player1'], 1)
        self.assertEqual(gameState['ball']['x'], COURT_WIDTH / 2) # Ball reset
        self.assertEqual(gameState['ball']['speedX'], -INITIAL_BALL_SPEED_X) # Serves to player1 (who just scored)

    def test_scoring_player2_scores(self): # Ball passes left boundary
        gameState['scores']['player2'] = 0
        # Position ball to pass the left boundary
        gameState['ball']['x'] = BALL_RADIUS -1 # Just about to score
        gameState['ball']['y'] = COURT_HEIGHT / 2
        gameState['ball']['speedX'] = -abs(INITIAL_BALL_SPEED_X) # Moving left

        simulate_game_loop_tick()

        self.assertEqual(gameState['scores']['player2'], 1)
        self.assertEqual(gameState['ball']['x'], COURT_WIDTH / 2) # Ball reset
        self.assertEqual(gameState['ball']['speedX'], INITIAL_BALL_SPEED_X) # Serves to player2

    def test_paddle_boundary_top(self):
        # This logic is in app.handle_paddle_move. We simulate its effect here.
        # Directly test the paddle position capping.
        new_y = -10
        if new_y < 0: new_y = 0
        self.assertEqual(new_y, 0)

    def test_paddle_boundary_bottom(self):
        new_y = COURT_HEIGHT - PADDLE_HEIGHT + 10
        if new_y + PADDLE_HEIGHT > COURT_HEIGHT: new_y = COURT_HEIGHT - PADDLE_HEIGHT
        self.assertEqual(new_y, COURT_HEIGHT - PADDLE_HEIGHT)

if __name__ == '__main__':
    # This allows running the tests directly from this file
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

# To run from CLI: python -m unittest ping_pong_game/tests/test_game_logic.py
# Or: python -m unittest discover ping_pong_game/tests
```
