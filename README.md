# LogTheLogger
LogTheLogger is an Open Source Discord Bot for Logging onto another Discord Server

Currently on Version 2.1 with comprehensive self-logging and database features
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
All configuration lives in a `.env` file. Copy `.env.example` to `.env` and set at least `DISCORD_TOKEN`.
Every option is explained in `.env.example`.

### With Docker (recommended, e.g. on an Ubuntu server)
1. Install Docker with the compose plugin
2. Clone this repository and create the config: `cp .env.example .env`, then fill in `DISCORD_TOKEN`
3. Create the data folder as your own user (the container runs as uid 1000): `mkdir data`
4. Start the bot: `docker compose up -d --build`
5. Follow the logs: `docker compose logs -f`

Updating: `git pull && docker compose up -d --build`.
The SQLite database is stored in `./data/ltl_database.db` and survives updates and restarts.

### Without Docker
1. Install [Python 3.13](https://www.python.org/downloads/) or later
2. `cp .env.example .env` and fill in `DISCORD_TOKEN`
3. `python -m pip install -r requirements.txt`
4. `python main.py` (on Windows you can use `start.bat`)

### Migrating from 2.0 (default_config.json)
`default_config.json` is no longer read. Move its values into `.env`:

| default_config.json | .env |
| --- | --- |
| `discordToken` | `DISCORD_TOKEN` |
| `discordServer` | `DISCORD_SERVER` |
| `discordStatusChannel` | `DISCORD_STATUS_CHANNEL` |
| `botOwner` | `BOT_OWNER` |
| `maintenanceMode` | `MAINTENANCE_MODE` |
| `discordInvite` | `DISCORD_INVITE` |

Copy your existing `ltl_database.db` into the `data` folder (or set `DATABASE_PATH` to its location).
Logs now go to the console; set `LOG_TO_FILE=true` to also write daily log files.

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