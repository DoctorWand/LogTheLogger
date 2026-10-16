import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BOT_VERSION = "2.1.0"

# Values already set in the environment (e.g. by docker compose) win over the .env file
if load_dotenv is not None:
    load_dotenv(override=False)


def _get_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int(name: str, default: int = 0) -> int:
    value = _get_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        sys.exit(f"Config error: {name} must be a number, got '{value}'")


def _get_bool(name: str, default: bool = False) -> bool:
    value = _get_str(name).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


# Discord
DISCORD_TOKEN = _get_str("DISCORD_TOKEN")
DISCORD_SERVER = _get_int("DISCORD_SERVER")
DISCORD_STATUS_CHANNEL = _get_int("DISCORD_STATUS_CHANNEL")
DEV_GUILD_ID = _get_int("DEV_GUILD_ID")
BOT_OWNER = _get_int("BOT_OWNER")
MAINTENANCE_MODE = _get_bool("MAINTENANCE_MODE")
DISCORD_INVITE = _get_str("DISCORD_INVITE", "https://discord.gg/mpgbu3M5Yy")

# Storage
DATA_DIR = _get_str("DATA_DIR", "data")
DATABASE_PATH = _get_str("DATABASE_PATH") or os.path.join(DATA_DIR, "ltl_database.db")

# Logging - stdout is always on; file logging is optional (not needed in Docker)
LOG_LEVEL = _get_str("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = _get_bool("LOG_TO_FILE")
LOG_DIR = _get_str("LOG_DIR") or os.path.join(DATA_DIR, "logs")
LOG_RETENTION_DAYS = _get_int("LOG_RETENTION_DAYS", 8)
TIMEZONE = _get_str("TIMEZONE", "Europe/Berlin")

# Optional heartbeat/health check server (needs heartbeat.py)
HEALTH_CHECK_PORT = _get_int("HEALTH_CHECK_PORT", 8000)


def require_token() -> str:
    if not DISCORD_TOKEN:
        sys.exit("Config error: DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    return DISCORD_TOKEN
