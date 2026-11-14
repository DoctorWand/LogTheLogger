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
6. Optional: use `/log-settings` to turn single event types on or off

## Permissions
### Bot
| Permission | Why | Required |
| --- | --- | --- |
| View Channels | The bot only receives message, reaction and pin events for channels it can see, and it has to see the log channel | yes, everywhere you want logs from |
| Send Messages | Posting logs, forwarded logs and forwarding requests | yes, in the log channel |
| Embed Links | Every log is an embed | yes, in the log channel |
| View Audit Log | Shows *who* changed roles, deleted a message, created/edited/deleted a channel or pinned a message | optional, otherwise `Unknown` |

Administrator is not needed. Invite scopes: `bot` and `applications.commands`, permission integer `19584` (`19456` without View Audit Log).
`/ltl_setup` refuses a log channel the bot can't post in.

### Users
All setup, forwarding and logging commands require **Manage Server** by default. Server admins can change who may use them under
Server Settings → Integrations → LogTheLogger. `/info`, `/ltl-help` and `/dev-discord` are open to everyone.

### Self-hosting
Enable the **Server Members** and **Message Content** privileged intents for your bot in the Discord Developer Portal.

## Running your own instance
All configuration lives in a `.env` file. Copy `.env.example` to `.env` and set at least `DISCORD_TOKEN`.
Every option is explained in `.env.example`.

### With Docker (recommended, e.g. on an Ubuntu server)
A ready-made image is published to `ghcr.io/doctorwand/logthelogger:latest` on every change to `main`.
You only need two files on the server: `docker-compose.yml` and `.env`.

1. Install Docker with the compose plugin
2. Copy `docker-compose.yml` and `.env.example` into a folder (for Dockge: the stack folder, e.g. `/opt/stacks/logthelogger`)
3. Rename `.env.example` to `.env` and fill in `DISCORD_TOKEN`
4. Create the data folder as your own user (the container runs as uid 1000): `mkdir data`
5. Start the bot: `docker compose up -d` (or "Start" in Dockge)
6. Follow the logs: `docker compose logs -f`

Updating: `docker compose pull && docker compose up -d`, or "Update" in Dockge.
The SQLite database is stored in `./data/ltl_database.db` and survives updates and restarts.

To build the image from a local checkout instead (for development):
`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`

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
- `/log-settings [log_type] [enabled]` - Show which event types are logged, or turn a single one on/off
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