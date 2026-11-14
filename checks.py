"""Small, Discord-independent checks so they can be unit tested."""
import datetime

# What the bot needs in a log channel to post a log there
LOG_CHANNEL_PERMISSIONS = (
    ("view_channel", "View Channel"),
    ("send_messages", "Send Messages"),
    ("embed_links", "Embed Links"),
)

# Audit log entries older than this are not attributed to a new event.
# Without a limit the lookup returned whoever did the same action last
# (e.g. a mod who deleted a message by that author an hour ago, even though
# the author deleted the new one themselves, which creates no audit entry).
AUDIT_MAX_AGE_SECONDS = 30


def missing_log_channel_permissions(permissions) -> list[str]:
    """Names of the permissions the bot is missing in a log channel."""
    return [label for attr, label in LOG_CHANNEL_PERMISSIONS if not getattr(permissions, attr, False)]


def is_recent_audit_entry(created_at: datetime.datetime, now: datetime.datetime,
                          max_age_seconds: float = AUDIT_MAX_AGE_SECONDS) -> bool:
    """True if an audit entry is young enough to belong to an event that just happened."""
    age = (now - created_at).total_seconds()
    # Small negative ages happen when the local clock is slightly behind Discord's
    return -5 <= age <= max_age_seconds
