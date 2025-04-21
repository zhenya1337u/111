# Discord Bot

A versatile Discord bot built with discord.py, providing moderation, utility, music, verification, and AI features.

## Features

- **Moderation Commands**: Ban, kick, warn, mute, and message purging
- **Utility Commands**: User info, server info, role management
- **Fun Commands**: 8ball, dice roll, memes, jokes
- **Music Player**: Play music in voice channels with queue management
- **Verification System**: Verify new members with captcha
- **AI Chat**: Chat with AI using OpenAI's API
- **Multilingual Support**: Available in English, Russian, and German

## Requirements

- Python 3.10+
- discord.py
- SQLAlchemy
- PostgreSQL database
- Other dependencies listed in `pyproject.toml`

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/discord-bot.git
   cd discord-bot
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install .
   ```

4. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file with your Discord token and other credentials.

6. Create a database and set up the connection string in `.env`.

## Configuration

1. Copy the example configuration file:
   ```
   cp refactored_bot/config/config.example.yaml refactored_bot/config/config.yaml
   ```

2. Edit `config.yaml` to customize bot settings.

## Running the Bot

```
python run_bot.py
```

## Project Structure

```
discord-bot/
├── refactored_bot/               # Main bot package
│   ├── cogs/                     # Command modules
│   │   ├── admin.py              # Admin commands
│   │   ├── ai.py                 # AI integration
│   │   ├── fun.py                # Fun commands
│   │   ├── moderation.py         # Moderation commands
│   │   ├── music.py              # Music player
│   │   ├── utility.py            # Utility commands
│   │   └── verification.py       # Verification system
│   ├── config/                   # Configuration files
│   │   └── config.example.yaml   # Example configuration
│   ├── core/                     # Core bot functionality
│   │   ├── bot.py                # Main bot class
│   │   └── config.py             # Configuration handling
│   ├── lang/                     # Language files
│   │   ├── en.json               # English
│   │   └── ru.json               # Russian
│   ├── models/                   # Database models
│   │   └── models.py             # SQLAlchemy models
│   ├── utils/                    # Utility modules
│   │   ├── db.py                 # Database utilities
│   │   ├── language.py           # Localization utilities
│   │   └── logger.py             # Logging utilities
│   ├── __init__.py               # Package initialization
│   └── main.py                   # Bot entry point
├── .env.example                  # Example environment variables
├── README.md                     # This file
└── run_bot.py                    # Bot execution script
```

## Commands

Here are some of the available commands:

### Moderation
- `!kick <user> [reason]` - Kick a user
- `!ban <user> [delete_days] [reason]` - Ban a user
- `!warn <user> [reason]` - Warn a user
- `!purge <amount> [user]` - Delete messages

### Utility
- `!userinfo [user]` - Show user information
- `!serverinfo` - Show server information
- `!avatar [user]` - Show user's avatar

### Fun
- `!8ball <question>` - Ask the Magic 8-Ball
- `!roll [NdM]` - Roll dice
- `!meme` - Get a random meme

### Music
- `!play <song>` - Play a song
- `!skip` - Skip the current song
- `!queue` - Show the current queue

### Verification
- `!verify` - Start verification
- `!setup_verification [channel]` - Set up verification

### AI
- `!ai <message>` - Chat with the AI
- `!aireset` - Reset AI conversation

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.