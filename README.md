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
3. On server A execute the `/forwarding-server` command and enter server B's id
    1. This sends a forwarding request to server B's log channel
4. On server B execute `/forwarding-accept` with server A's id
    1. From now on the logs from server A show up on server B
5. Use `/self-logging true` to enable the bot's own event logging

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
4. `python main.py`

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
- `/forwarding-server <server_id>` - Request to forward your logs to another server
- `/forwarding-accept <server_id>` - Accept a forwarding request from another server
- `/forwarding-deny <server_id>` - Deny a request or stop logs coming from another server
- `/forwarding-list` - Show outgoing and incoming forwarding links and their status
- `/delete-forwarding-server <server_id>` - Stop forwarding your logs to a server
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

## Use of AI
Parts of this project are developed with AI assistance (Claude by Anthropic, via Claude Code).

- **Up to version 2.0:** written by DoctorWand, with occasional AI help for minor bug fixes.
- **From version 2.1 (October 2026):** the restructuring was planned and largely written by Claude. That covers the `.env` configuration, the Docker setup, the startup bug fixes and the forwarding consent. DoctorWand set the direction, reviewed the changes and decided what gets merged.

Commits written with AI carry a `Co-Authored-By: Claude` line, so `git log` shows exactly which changes were AI-assisted.
Nothing gets merged without a human review. Bugs are still the maintainer's responsibility, so please report them like any other issue.

## License
This project is open source. See the repository for license details.