# Ping Pong Online Game

This directory contains a simple online Ping Pong game implemented using HTML, CSS, JavaScript, and a Python Flask-SocketIO backend.

## Setup and Installation

### 1. Prerequisites
*   Python 3.7+
*   `pip` (Python package installer)

### 2. Create a Virtual Environment (Recommended)
It's good practice to create a virtual environment for Python projects to manage dependencies separately.

```bash
# Navigate to the ping_pong_game directory (if not already there)
cd path/to/your/repository/ping_pong_game

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS and Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies
With the virtual environment activated, install the required Python packages:

```bash
pip install Flask Flask-SocketIO
```
If you encounter issues with `eventlet` or `gevent` during installation on certain systems, you might need to install them explicitly or ensure you have the necessary build tools.
`Flask-SocketIO` will try to use `eventlet` if available, then `gevent`, and finally the Werkzeug development server. For production, `eventlet` or `gevent` are recommended.

### 4. Running the Application
Once the dependencies are installed, you can run the main application server:

```bash
python app.py
```
The server will typically start on `http://127.0.0.1:5000/` or `http://0.0.0.0:5000/`.
Open this URL in your web browser to play the game.

The server will print "Client connected" and "Client disconnected" messages to the console when users open and close the game page.

### Alternative: Static Development Server
A simple Python HTTP server (`dev_server.py`) is also included for serving static files directly without the SocketIO backend. This might be useful for very early UI development if the backend is not needed.

To run it:
```bash
python dev_server.py
```
This server typically runs on `http://127.0.0.1:8000/`.

## Running Unit Tests

The project includes unit tests for the server-side game logic. These tests verify functionalities like ball movement, collision detection, scoring, and game state management.

To run the tests:
1.  Ensure your virtual environment is activated (if you created one).
2.  Navigate to the root of the repository (the directory containing `ping_pong_game`).
3.  Run the tests using Python's `unittest` module:

    ```bash
    python -m unittest discover ping_pong_game/tests
    ```
    Alternatively, you can run a specific test file:
    ```bash
    python -m unittest ping_pong_game/tests/test_game_logic.py
    ```

    The tests should execute and report their status (e.g., "OK" if all pass).

## Project Structure
*   `app.py`: The main Flask-SocketIO application server.
*   `dev_server.py`: A simple Python HTTP server for static file development.
*   `index.html`: The main HTML file for the game.
*   `style.css`: CSS styles for the game.
*   `script.js`: JavaScript game logic (client-side).
*   `README.md`: This file.
*   `tests/`: Directory containing unit tests.
    *   `tests/__init__.py`: Makes the `tests` directory a Python package.
    *   `tests/test_game_logic.py`: Unit tests for `app.py`.
