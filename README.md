# LogTheLogger
LogTheLogger is an Open Source Discord Bot for Logging onto another Discord Server

Currently on Version 2.0 with comprehensive self-logging and database features
- See [ROADMAP](ROADMAP.md) for more information

## Dev/Support Discord
> [!TIP]
> If you can't figure something out, feel free to join the discord
> https://discord.gg/mpgbu3M5Yy

## Features
- **Log Forwarding**: Forward logs from one Discord server to another
- **Self Logging**: Comprehensive logging of Discord events (messages, members, reactions, voice, etc.)
- **Database Management**: SQLite database with configurable log settings per guild
- **Multi-Server Support**: Forward logs to multiple servers simultaneously
- **Granular Control**: Enable/disable specific log types per server

## How to setup
1. Invite the Bot on both servers
2. Execute on both servers the `/ltl_setup` command and enter your log channels
3. On the main server execute the `/forwarding-server` command and enter the second server id
    1. With executing this command you should start seeing the logs from server A on server B
4. Use `/self-logging true` to enable the bot's own event logging
5. Configure specific log types using the database settings

## Running your own instance
1. Install [Python 3.13.3](https://www.python.org/downloads/release/python-3133/) or later
2. Fill out the `default_config.json`:
    1. `"discordToken"` -> Your Discord bot token
    2. `"discordServer"` -> Your server id
    3. `"discordStatusChannel"` -> Your status channel (if you don't have one, leave as 0)
3. Run `install-requirements.bat` to install all dependencies
4. Start the bot with `start.bat` or run `python main.py`

> [!IMPORTANT]
> Make sure you have Python 3.13.3 or later installed and added to your PATH.
> Simply run `install-requirements.bat` to install all required dependencies automatically.

## Commands
- `/ltl_setup` - Initial bot setup with log channel configuration
- `/ltl_revoke_setup` - Remove bot configuration from server
- `/forwarding <true/false>` - Enable/disable log forwarding
- `/forwarding-server <server_id>` - Add server to forwarding list
- `/delete-forwarding-server <server_id>` - Remove server from forwarding list
- `/self-logging <true/false>` - Enable/disable self event logging
- `/info` - Display bot information
- `/ltl-help` - Show detailed help information

## Configuration
The bot uses a SQLite database to store:
- Guild configurations (log channels, forwarding settings)
- Individual log type settings (message edits, member joins, reactions, etc.)
- Multi-server forwarding relationships

## Contributing
Feel free to contribute to this project by:
- Reporting bugs and issues
- Suggesting new features
- Submitting pull requests
- Improving documentation

## License
This project is open source. See the repository for license details.