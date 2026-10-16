# Imports
import discord
import time
import datetime
import difflib
import os
import re
import sys
import logging
import pytz

# From x import y
from discord import app_commands
from discord.ext import commands
from discord.ext.tasks import loop
from logging.handlers import TimedRotatingFileHandler
import config
from db_handler import db
try:
    from heartbeat import Heartbeat
except ImportError:
    Heartbeat = None

# Setup logging - always to stdout (Docker / process manager picks it up),
# optionally also to daily rotating files when LOG_TO_FILE is enabled
LOG_DIR = config.LOG_DIR
BASE_LOG_NAME = "JASTBI-LogTheLogger"
RETENTION_DAYS = config.LOG_RETENTION_DAYS
TIMEZONE = config.TIMEZONE

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)
if not logger.hasHandlers():
    formatter = logging.Formatter(datefmt='%d.%m.%Y %H:%M:%S',fmt='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if config.LOG_TO_FILE:
        os.makedirs(LOG_DIR,exist_ok=True)
        # backupCount=0 disables the handler's own (system-local-time-based) deletion.
        # clean_old_logs() is the single source of truth for retention, using TIMEZONE
        # explicitly - two independent cleanup schedules previously caused stale files
        # to stick around or vanish at the wrong time depending on the host's system clock.
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(LOG_DIR,BASE_LOG_NAME),
            when="midnight",
            interval=1,
            backupCount=0,
            encoding="utf-8",
            utc=False
        )
        file_handler.suffix = "%d.%m.%Y.log"
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

# Clear Old Logs
def clean_old_logs(directory, base_name, retention_days, timezone=TIMEZONE):
    cutoff = datetime.datetime.now(pytz.timezone(timezone)) - datetime.timedelta(days=retention_days)
    pattern = re.compile(rf"{re.escape(base_name)}.(\d{{2}}.\d{{2}}.\d{{4}})\.log")
    logs_deleted = False

    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            date_str = match.group(1)
            try:
                file_date = datetime.datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=pytz.timezone(timezone))
                if file_date < cutoff:
                    full_path = os.path.join(directory,filename)
                    os.remove(full_path)
                    
                    logger.info(f"Deleted old log: {full_path}")
                    logs_deleted = True
            except Exception as e:
                logger.warning(f"Error - Log {filename} couldn't be deleted, Error: {e}")
                raise e
    
    if not logs_deleted:
        logger.info("No old logs found")

# Runtime config
main_server = config.DISCORD_SERVER
main_statusChannel = config.DISCORD_STATUS_CHANNEL
bot_owner = config.BOT_OWNER
# Runtime only: toggled by /maintenance, reset to MAINTENANCE_MODE on restart
maintenance = config.MAINTENANCE_MODE

# Embed descriptions are capped by Discord at 4096 characters
MAX_EMBED_DESCRIPTION = 4096

heartbeat_instance = None

# Getting base embed
def get_embed(title:str,description:str) -> discord.Embed:
    # Must be timezone-aware: a naive datetime gets serialized without a UTC offset,
    # so Discord assumes UTC on display - on a host not running in UTC this silently
    # shifted every logged timestamp by the host's offset (occasionally showing as
    # a log from hours in the past/future).
    if description and len(description) > MAX_EMBED_DESCRIPTION:
        description = description[:MAX_EMBED_DESCRIPTION - 3] + "..."
    embed = discord.Embed(title=title,description=description,timestamp=datetime.datetime.now(datetime.timezone.utc))
    return embed

# Builds a clickable jump-to-message link
def build_message_link(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

# Word-level diff between the old and new content of an edited message.
# Falls back to None (caller should show full Before/After) when the change
# is too large to summarize usefully as a word diff.
MAX_WORD_DIFF_CHANGES = 6

def diff_message_content(before: str, after: str) -> str | None:
    before_words = before.split()
    after_words = after.split()
    matcher = difflib.SequenceMatcher(None, before_words, after_words)

    parts = []
    changed_word_count = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed = before_words[i1:i2]
        added = after_words[j1:j2]
        changed_word_count += max(len(removed), len(added))
        if changed_word_count > MAX_WORD_DIFF_CHANGES:
            return None

        if tag == "replace":
            parts.append(f"{' '.join(removed)}->{' '.join(added)}")
        elif tag == "delete":
            parts.append(f"-{' '.join(removed)}")
        elif tag == "insert":
            parts.append(f"+{' '.join(added)}")

    if not parts:
        return None
    return " ; ".join(parts)

# External Logging 
def loggingFromExternal(type: str, message: str):
    type = type.lower()
    if type == "info":
        logger.info(message)
    elif type == "warn":
        logger.warning(message)
    else:
        logger.error(message)

# The Magic
class DiscordBot(commands.Bot):
    startup_time: float = 0.0

    async def _get_audit_actor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        try:
            if not guild.me or not guild.me.guild_permissions.view_audit_log:
                return None
            async for entry in guild.audit_logs(limit=10, action=action):
                target = getattr(entry, "target", None)
                if getattr(target, "id", None) == target_id:
                    return entry.user
        except Exception:
            return None
        return None

    # setup_hook runs exactly once before connecting; on_ready fires again on every
    # reconnect, which previously re-registered commands (CommandAlreadyRegistered)
    # and re-started already running loops (RuntimeError).
    async def setup_hook(self):
        startup_time_start = time.time()
        try:
            bot_commands(self)
        except Exception as e:
            logger.error(f"Setup Command Error: {e}")
            raise e
        logger.info("~Start Syncing Commands~")
        try:
            if config.DEV_GUILD_ID:
                dev_guild = discord.Object(id=config.DEV_GUILD_ID)
                self.tree.copy_global_to(guild=dev_guild)
                await self.tree.sync(guild=dev_guild)
            if main_server and main_server != config.DEV_GUILD_ID:
                await self.tree.sync(guild=discord.Object(id=main_server))
            await self.tree.sync()
            logger.info("Synced Commands successfully")
        except Exception as e:
            logger.error(f"Sync Commands | Error: {e}")
            raise e
        logger.info("~End Syncing Commands~")
        loops(self)
        self.startup_time = round((time.time() - startup_time_start)*1000,2)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} | ID: {self.user.id} | Guilds: {len(self.guilds)} | Startup-Time: {self.startup_time} Milliseconds.")

    async def on_message(self,message):
        if message.author == self.user or message.guild is None:
            return
        guild_id = message.guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["logForwarding"]:
            return

        if message.channel.id == guild_config["logChannel"]:
            for embed in message.embeds:
                for forward_guild in guild_config["logSendingToServerId"]:
                    await self.forwarding_embeds(forward_guild, embed, message.guild.id)
        return

    async def on_guild_join(self,guild):
        # Global commands are available in new guilds automatically, no sync needed
        logger.info(f"Joined Guild | {guild.name} | {guild.id}")
        return

    # discord.py has no on_guild_leave event - on_guild_remove is the real one
    async def on_guild_remove(self, guild):
        if db.check_if_guild_exists(guild.id):
            db.remove_guild(guild.id)
            logger.info(f"Left Guild | {guild.id} | Removed from Database")
        return

    async def send_status(self,status,info):
        guild = self.get_guild(main_server)
        channel = guild.get_channel(main_statusChannel) if guild else None
        if channel is None:
            logger.warning(f"send_status | status channel {main_statusChannel} not found")
            return
        embed = get_embed(status,info)
        return await channel.send(embed=embed)

    async def send_logs(self, guild_id: int, title: str, log: str):
        guild = self.get_guild(guild_id)
        guild_config = db.get_guild_config(guild_id)
        channel = guild.get_channel(guild_config["logChannel"]) if guild else None
        embed = get_embed(title, log)
        embed.set_author(name=guild.name if guild else str(guild_id), icon_url=(guild.icon if guild else None))

        if not guild_config["onlyForwarding"]:
            if channel is None:
                logger.warning(
                    f"send_logs | guild={guild_id} ({guild.name if guild else 'Unknown'}) | logChannel not found: {guild_config['logChannel']}"
                )
            else:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden as e:
                    logger.warning(
                        f"send_logs | guild={guild_id} ({guild.name if guild else 'Unknown'}) | Missing Access to send in channel={channel.id}: {e}"
                    )
                except discord.HTTPException as e:
                    logger.warning(
                        f"send_logs | guild={guild_id} ({guild.name if guild else 'Unknown'}) | HTTPException sending log: {e}"
                    )

        for forwarding_guild in guild_config["logSendingToServerId"]:
            try:
                await self.forwarding_embeds(forwarding_guild, embed, guild_id)
            except discord.Forbidden as e:
                to_guild = self.get_guild(forwarding_guild)
                logger.warning(
                    f"send_logs | from_guild={guild_id} ({guild.name if guild else 'Unknown'}) -> to_guild={forwarding_guild} ({to_guild.name if to_guild else 'Unknown'}) | Missing Access: {e}"
                )
            except discord.HTTPException as e:
                to_guild = self.get_guild(forwarding_guild)
                logger.warning(
                    f"send_logs | from_guild={guild_id} ({guild.name if guild else 'Unknown'}) -> to_guild={forwarding_guild} ({to_guild.name if to_guild else 'Unknown'}) | HTTPException: {e}"
                )
            except Exception as e:
                to_guild = self.get_guild(forwarding_guild)
                logger.warning(
                    f"send_logs | from_guild={guild_id} ({guild.name if guild else 'Unknown'}) -> to_guild={forwarding_guild} ({to_guild.name if to_guild else 'Unknown'}) | Unexpected error: {e}"
                )
        return

    async def forwarding_embeds(self, guild_id: int, embed: discord.Embed, from_guild_id: int):
        if not db.check_if_guild_exists(guild_id):
            return

        guild = self.get_guild(guild_id)
        from_guild = self.get_guild(from_guild_id)
        to_name = guild.name if guild else "Unknown"
        from_name = from_guild.name if from_guild else "Unknown"

        if guild is None or from_guild is None:
            logger.warning(
                f"forwarding_embeds | guild not found. to={guild_id} ({to_name}) from={from_guild_id} ({from_name})"
            )
            return

        guild_config = db.get_guild_config(guild_id)
        channel = guild.get_channel(guild_config["logChannel"])
        if channel is None:
            logger.warning(
                f"forwarding_embeds | to_guild={guild_id} ({to_name}) | logChannel not found: {guild_config['logChannel']}"
            )
            return

        embed.set_author(name=from_guild.name, icon_url=from_guild.icon)
        embed.set_footer(text=f"From Server: {from_guild.name}")
        try:
            return await channel.send(embed=embed)
        except discord.Forbidden as e:
            logger.warning(
                f"forwarding_embeds | to_guild={guild_id} ({to_name}) | Missing Access to send in channel={channel.id}: {e}"
            )
            return
        except discord.HTTPException as e:
            logger.warning(
                f"forwarding_embeds | to_guild={guild_id} ({to_name}) | HTTPException: {e}"
            )
            return

    # Discord Event Logging
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.user.id:
            return

        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageReactionAdd"]:
            return

        guild = self.get_guild(guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        member_str = f"{member} | {member.id}" if member else f"Unknown Member | {payload.user_id}"

        channel = guild.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"

        message_id = payload.message_id

        emoji = str(payload.emoji)
        if len(emoji) > 100:
            emoji = emoji[:97] + "..."

        link = build_message_link(guild_id, payload.channel_id, message_id)
        log = (
            f"**User:** {member_str}\n"
            f"**Channel:** {channel_str}\n"
            f"**Message ID:** {message_id}\n"
            f"**Emoji:** {emoji}\n"
            f"**Link:** [Jump to Message]({link})"
        )
        await self.send_logs(guild_id, "Reaction Added", log)
        return

    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.user.id:
            return

        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageReactionRemove"]:
            return

        guild = self.get_guild(guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        member_str = f"{member} | {member.id}" if member else f"Unknown Member | {payload.user_id}"

        channel = guild.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"

        message_id = payload.message_id

        emoji = str(payload.emoji)
        if len(emoji) > 100:
            emoji = emoji[:97] + "..."

        link = build_message_link(guild_id, payload.channel_id, message_id)
        log = (
            f"**User:** {member_str}\n"
            f"**Channel:** {channel_str}\n"
            f"**Message ID:** {message_id}\n"
            f"**Emoji:** {emoji}\n"
            f"**Link:** [Jump to Message]({link})"
        )
        await self.send_logs(guild_id, "Reaction Removed", log)
        return

    async def on_raw_reaction_clear(self, payload):
        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageReactionClear"]:
            return

        guild = self.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"

        message_id = payload.message_id

        link = build_message_link(guild_id, payload.channel_id, message_id)
        log = (
            f"**Channel:** {channel_str}\n"
            f"**Message ID:** {message_id}\n"
            f"**Link:** [Jump to Message]({link})"
        )
        await self.send_logs(guild_id, "Reactions Cleared", log)
        return
    
    async def on_member_join(self, member):
        guild_id = member.guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["memberJoin"]:
            return

        log = f"**User:** {member} | {member.id}\n**Account Created:** {member.created_at.strftime('%d.%m.%Y %H:%M:%S')}\n**Member Count:** {member.guild.member_count}"
        await self.send_logs(guild_id, "Member Joined", log)
        return

    async def on_raw_member_remove(self, payload):
        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["memberLeave"]:
            return

        guild = self.get_guild(guild_id)

        member_count = guild.member_count if guild else "Unknown"
        log = f"**User ID:** {payload.user.id}\n**User Name:** {payload.user.name}\n**Member Count:** {member_count}"
        await self.send_logs(guild_id, "Member Left", log)
        return
    
    async def on_member_ban(self, guild, user):
        guild_id = guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["memberBan"]:
            return

        log = f"**User:** {user} | {user.id}"
        await self.send_logs(guild_id, "Member Banned", log)
        return

    async def on_member_unban(self, guild, user):
        guild_id = guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["memberUnban"]:
            return

        log = f"**User:** {user} | {user.id}"
        await self.send_logs(guild_id, "Member Unbanned", log)
        return
    
    async def on_member_update(self, before, after):
        guild_id = before.guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["memberUpdate"]:
            return

        changes = []
        if before.nick != after.nick:
            changes.append(f"**Nickname:** {before.nick} -> {after.nick}")

        if before.roles != after.roles:
            before_role_ids = {r.id for r in before.roles if r.name != "@everyone"}
            after_role_ids = {r.id for r in after.roles if r.name != "@everyone"}

            added_ids = after_role_ids - before_role_ids
            removed_ids = before_role_ids - after_role_ids

            added_roles = [r.mention for r in after.roles if r.id in added_ids]
            removed_roles = [r.name for r in before.roles if r.id in removed_ids]

            role_lines = []
            if added_roles:
                role_lines.append(f"**Roles Added:** {', '.join(added_roles)}")
            if removed_roles:
                role_lines.append(f"**Roles Removed:** {', '.join(removed_roles)}")

            # Best-effort: who changed roles (audit log, requires View Audit Log)
            actor = await self._get_audit_actor(after.guild, discord.AuditLogAction.member_role_update, after.id)
            actor_str = f"{actor} | {actor.id}" if actor else "Unknown"

            if role_lines:
                changes.append("\n".join(role_lines) + f"\n**Changed By:** {actor_str}")

        if before.pending != after.pending:
            changes.append(f"**Membership Screening:** {before.pending} -> {after.pending}")

        if before.avatar != after.avatar:
            before_avatar = before.avatar.url if before.avatar else "No Avatar"
            after_avatar = after.avatar.url if after.avatar else "No Avatar"
            changes.append(f"**Avatar Changed:** [Before]({before_avatar}) -> [After]({after_avatar})")

        if changes:
            log = f"**User:** {before} | {before.id}\n" + "\n".join(changes)
            await self.send_logs(guild_id, "Member Updated", log)
        return
    
    async def on_raw_message_delete(self, payload):
        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageDelete"]:
            return

        channel = self.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"
        message_id = payload.message_id
        author = payload.cached_message.author if payload.cached_message else None
        author_str = f"{author} | {author.id}" if author else "Unknown"
        cached_message = payload.cached_message.content if payload.cached_message else "Content not cached"

        deleter = None
        guild = self.get_guild(guild_id)
        if guild is not None and author is not None:
            deleter = await self._get_audit_actor(guild, discord.AuditLogAction.message_delete, author.id)

        link = build_message_link(guild_id, payload.channel_id, message_id)
        lines = [
            f"**Channel:** {channel_str}",
            f"**Author:** {author_str}",
        ]
        # Skip the separate line when the author deleted their own message - same ID twice is noise.
        if not (author is not None and deleter is not None and deleter.id == author.id):
            deleted_by_str = f"{deleter} | {deleter.id}" if deleter else "Unknown"
            lines.append(f"**Deleted By:** {deleted_by_str}")
        lines += [
            f"**Message:** {cached_message}",
            f"**Message ID:** {message_id}",
            f"**Link:** [Jump to Message]({link})",
        ]
        await self.send_logs(guild_id, "Message Delete", "\n".join(lines))
        return
    
    async def on_raw_bulk_message_delete(self, payload):
        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageBulkDelete"]:
            return

        channel = self.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"
        message_ids = payload.message_ids

        MAX_LINKS = 15
        links = [
            f"[{mid}]({build_message_link(guild_id, payload.channel_id, mid)})"
            for mid in list(message_ids)[:MAX_LINKS]
        ]
        links_str = ", ".join(links)
        if len(message_ids) > MAX_LINKS:
            links_str += f" (+{len(message_ids) - MAX_LINKS} more)"

        log = (
            f"**Channel:** {channel_str}\n"
            f"**Message IDs:** {', '.join(map(str, message_ids))}\n"
            f"**Links:** {links_str}"
        )
        await self.send_logs(guild_id, "Bulk Message Delete", log)
        return

    async def on_raw_message_edit(self, payload):
        if payload.data.get("author", {}).get("id") == str(self.user.id):
            return

        # Discord also fires this event when a message's embed refreshes/unfurls
        # with no text edit (e.g. our own "Jump to Message" links re-unfurling
        # days later) - that payload can still carry "content" (unchanged/empty)
        # and often omits "author" entirely, so neither is reliable on its own.
        # "edited_timestamp" is only ever set by Discord on a genuine text edit.
        if not payload.data.get("edited_timestamp"):
            return

        # Discord only includes "content" when the text itself changed - edits
        # that only touch embeds/pins/etc. send a partial payload without it.
        if "content" not in payload.data:
            return

        guild_id = payload.guild_id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["messageUpdate"]:
            return

        guild = self.get_guild(guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        channel_str = f"{channel.mention} | {channel.id}" if channel else f"Unknown Channel | {payload.channel_id}"

        before_content = payload.cached_message.content if payload.cached_message else None
        after_content = payload.data.get("content", "")

        if before_content is not None and before_content == after_content:
            return

        author_id = payload.data.get("author", {}).get("id")
        author = guild.get_member(int(author_id)) if author_id else "Unknown User"

        link = build_message_link(guild_id, payload.channel_id, payload.message_id)
        content_diff = diff_message_content(before_content, after_content) if before_content is not None else None

        if content_diff is not None:
            content_lines = f"**Changed:** {content_diff}"
        else:
            before_display = before_content if before_content is not None else "Content not cached"
            content_lines = f"**Before:** {before_display}\n**After:** {after_content}"

        log = (
            f"**User:** {author}\n"
            f"**Channel:** {channel_str}\n"
            f"**Message ID:** {payload.message_id}\n"
            f"{content_lines}\n"
            f"**Link:** [Jump to Message]({link})"
        )
        await self.send_logs(guild_id, "Message Updated", log)
        return
    
    async def on_voice_state_update(self, member, before, after):
        guild_id = member.guild.id
        if not db.check_if_guild_exists(guild_id):
            return
        
        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return
            
        log_settings = db.get_log_settings(guild_id)

        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                if not log_settings["voiceChannelJoin"]:
                    return
                log = f"**User:** {member.mention}\n**Channel:** {after.channel.mention}"
                await self.send_logs(guild_id, "Voice Channel Joined", log)
            elif before.channel is not None and after.channel is None:
                if not log_settings["voiceChannelLeave"]:
                    return
                log = f"**User:** {member.mention}\n**Channel:** {before.channel.mention}"
                await self.send_logs(guild_id, "Voice Channel Left", log)
            elif before.channel is not None and after.channel is not None:
                if not log_settings["voiceChannelMove"]:
                    return
                log = f"**User:** {member.mention}\n**From Channel:** {before.channel.mention}\n**To Channel:** {after.channel.mention}"
                await self.send_logs(guild_id, "Voice Channel Moved", log)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild_id = channel.guild.id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["channelCreate"]:
            return

        actor = await self._get_audit_actor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        actor_str = f"{actor} | {actor.id}" if actor else "Unknown"

        log = (
            f"**Channel:** {channel.mention} | {channel.id}\n"
            f"**Type:** {getattr(channel.type, 'name', str(channel.type))}\n"
            f"**Category:** {channel.category.name if getattr(channel, 'category', None) else 'None'}\n"
            f"**Created By:** {actor_str}"
        )
        await self.send_logs(guild_id, "Channel Created", log)
        return

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild_id = channel.guild.id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["channelDelete"]:
            return

        actor = await self._get_audit_actor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        actor_str = f"{actor} | {actor.id}" if actor else "Unknown"

        # channel.mention will not be valid for deleted channels; show name + id
        log = (
            f"**Channel:** #{channel.name} | {channel.id}\n"
            f"**Type:** {getattr(channel.type, 'name', str(channel.type))}\n"
            f"**Category:** {channel.category.name if getattr(channel, 'category', None) else 'None'}\n"
            f"**Deleted By:** {actor_str}"
        )
        await self.send_logs(guild_id, "Channel Deleted", log)
        return

    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild_id = after.guild.id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings["channelUpdate"]:
            return

        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** {before.name} -> {after.name}")

        before_category = before.category.name if getattr(before, 'category', None) else None
        after_category = after.category.name if getattr(after, 'category', None) else None
        if before_category != after_category:
            changes.append(f"**Category:** {before_category or 'None'} -> {after_category or 'None'}")

        before_pos = getattr(before, 'position', None)
        after_pos = getattr(after, 'position', None)
        if before_pos != after_pos:
            changes.append(f"**Position:** {before_pos} -> {after_pos}")

        before_nsfw = getattr(before, 'nsfw', None)
        after_nsfw = getattr(after, 'nsfw', None)
        if before_nsfw != after_nsfw:
            changes.append(f"**NSFW:** {before_nsfw} -> {after_nsfw}")

        # Text channel specific fields
        before_topic = getattr(before, 'topic', None)
        after_topic = getattr(after, 'topic', None)
        if before_topic != after_topic:
            changes.append(f"**Topic:** {before_topic or 'None'} -> {after_topic or 'None'}")

        before_slowmode = getattr(before, 'slowmode_delay', None)
        after_slowmode = getattr(after, 'slowmode_delay', None)
        if before_slowmode != after_slowmode:
            changes.append(f"**Slowmode:** {before_slowmode} -> {after_slowmode}")

        if not changes:
            return

        actor = await self._get_audit_actor(after.guild, discord.AuditLogAction.channel_update, after.id)
        actor_str = f"{actor} | {actor.id}" if actor else "Unknown"

        mention = getattr(after, 'mention', f"#{after.name}")
        log = (
            f"**Channel:** {mention} | {after.id}\n"
            + "\n".join(changes)
            + f"\n**Edited By:** {actor_str}"
        )
        await self.send_logs(guild_id, "Channel Updated", log)
        return

    async def on_guild_channel_pins_update(self, channel: discord.abc.GuildChannel, last_pin: datetime.datetime | None):
        guild_id = channel.guild.id
        if not db.check_if_guild_exists(guild_id):
            return

        guild_config = db.get_guild_config(guild_id)
        if not guild_config["selfLogging"]:
            return

        log_settings = db.get_log_settings(guild_id)
        if not log_settings.get("messageUpdate", False):
            return

        actor = await self._get_audit_actor(channel.guild, discord.AuditLogAction.message_pin, channel.id)
        actor_str = f"{actor} | {actor.id}" if actor else "Unknown"

        last_pin_str = last_pin.strftime('%d.%m.%Y %H:%M:%S') if last_pin else "None"
        log = (
            f"**Channel:** {channel.mention} | {channel.id}\n"
            f"**Last Pin:** {last_pin_str}\n"
            f"**By:** {actor_str}"
        )
        await self.send_logs(guild_id, "Channel Pins Updated", log)
        return

# Automation Tasks
def loops(client):
    @loop(hours=12)
    async def clear_old_logs():
        if not config.LOG_TO_FILE:
            return
        clean_old_logs(LOG_DIR,BASE_LOG_NAME,RETENTION_DAYS)
        logger.info(f"Checked for Old Logs - {datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m.%Y | %H:%M:%S')}")

    @loop(seconds=60)
    async def uptime_heartbeat():
        if Heartbeat is None:
            return
        global heartbeat_instance
        if heartbeat_instance is None:
            try:
                heartbeat_instance = Heartbeat(client, port=config.HEALTH_CHECK_PORT)
                await heartbeat_instance.start()
                logger.info("Heartbeat Server initialisiert und gestartet")
            except Exception as e:
                logger.error(f"Fehler beim Starten des Heartbeat Servers: {e}")
                return
        try:
            if not client.is_ready():
                logger.warning("Bot ist nicht bereit")
            else:
                logger.debug(f"Heartbeat aktiv - Bot läuft mit {len(client.guilds)} Servern")
        except Exception as e:
            logger.error(f"Fehler im Heartbeat Loop: {e}")

    uptime_heartbeat.start()
    
    @uptime_heartbeat.before_loop
    async def before_heartbeat():
        await client.wait_until_ready()


    clear_old_logs.start()
        
# Slash Commands
def bot_commands(client):
    @client.tree.command(name="info",description="Get some Information about the Bot")
    @app_commands.checks.cooldown(1,10.0)
    async def info(interaction: discord.Interaction):
        embed = discord.Embed(title="LogTheLogger",description="A simple Logging Bot with Log Forwarding",timestamp=datetime.datetime.now())
        embed.add_field(name="Developer",value="DoctorWand, part of JASTBI")
        embed.add_field(name="Library",value="discord.py")
        embed.add_field(name="Source Code",value="[GitHub](https://github.com/DoctorWand/LogTheLogger)")
        embed.add_field(name="TopGG",value="[Vote](https://top.gg/bot/1345485578279325737/vote)")
        embed.add_field(name="Support Server",value="[Discord](https://discord.gg/mpgbu3M5Yy)")
        embed.set_thumbnail(url=client.user.display_avatar)
        embed.set_footer(text="LogTheLogger | Developed by DoctorWand")
        return await interaction.response.send_message(embed=embed)

    @client.tree.command(name="ltl_setup",description="Initial Setup.")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    @app_commands.describe(logchannel = "The Channel where logs are getting send to.")
    async def ltl_setup(interaction: discord.Interaction, logchannel: discord.TextChannel):
        guild_id = interaction.guild.id
        if db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="Setup was already executed")
            
        db.init_new_guild(guild_id, interaction.guild.name)
        db.update_guild_config(guild_id, logChannel=logchannel.id)
        
        logger.info(f"Setup executed for {interaction.guild.name} | {guild_id}")
        await interaction.response.send_message(content=f"Setup was completed for ***{interaction.guild}*** | ***{guild_id}***")
        await client.send_logs(guild_id, "Setup", "completed successfully")

    @client.tree.command(name="ltl_revoke_setup",description="Clears the Setup if you messed up")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def ltlRevokeSetup(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if not db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
        
        db.remove_guild(guild_id)
        logger.info(f"Setup revoked for {interaction.guild.name} | {guild_id}")
        return await interaction.response.send_message(content="Setup was revoked successfully")

    @client.tree.command(name="forwarding",description="Enable/Disable Log Forwarding")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwarding(interaction: discord.Interaction, forwarding: bool=True):
        guild_id = interaction.guild.id
        if not db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
            
        db.update_guild_config(guild_id, logForwarding=forwarding)
        logger.info(f"Forwarding set to {forwarding} for {interaction.guild.name} | {guild_id}")
        await client.send_logs(guild_id, "Forwarding", f"was set to {forwarding}")
        return await interaction.response.send_message(content=f"Forwarding Statement is now: {forwarding}")

    @client.tree.command(name="forwarding-server",description="The Server you want to get it forwarded")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwardingServer(interaction: discord.Interaction, server_id: str):
        if not server_id.isdigit():
            return await interaction.response.send_message(content="Please enter a server id and not a server name")
            
        server_id_int = int(server_id)
        guild_id = interaction.guild.id
        
        if guild_id == server_id_int:
            return await interaction.response.send_message(content="Forwarding Logs onto the same Server isn't possible", ephemeral=True)
            
        if not db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
            
        if not db.check_if_guild_exists(server_id_int):
            return await interaction.response.send_message(content="The /setup command wasn't executed on the other server yet!")

        target_guild = client.get_guild(server_id_int)
        if target_guild is None:
            return await interaction.response.send_message(content="The bot is not on the other server anymore", ephemeral=True)
            
        guild_config = db.get_guild_config(guild_id)
        current_list = guild_config["logSendingToServerId"]
        
        if server_id_int in current_list:
            return await interaction.response.send_message(content="Server is already in forwarding list")
            
        current_list.append(server_id_int)
        db.update_guild_config(guild_id, logSendingToServerId=current_list)
        
        logger.info(f"Added Forwarding Server {server_id_int} for {interaction.guild.name} | {guild_id}")
        await interaction.response.send_message(content=f"The Server {target_guild.name} | {server_id_int} was added successfully")
        await client.send_logs(guild_id, "Forwarding-Server", f"{target_guild.name} was added to the forwarding list")
    
    @client.tree.command(name="delete-forwarding-server",description="Deletes a Server from the forwarding list")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def deleteForwardingServer(interaction: discord.Interaction, server_id: str):
        if not server_id.isdigit():
            return await interaction.response.send_message(content="Please enter a server-id and not a server-name")
            
        guild_id = interaction.guild.id
        server_id_int = int(server_id)

        if not db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")

        guild_config = db.get_guild_config(guild_id)
        current_list = guild_config["logSendingToServerId"]
        
        if server_id_int not in current_list:
            return await interaction.response.send_message(content="The server-id you provided is not in the database for your server")
            
        current_list.remove(server_id_int)
        db.update_guild_config(guild_id, logSendingToServerId=current_list)
        
        target_guild = client.get_guild(server_id_int)
        target_name = target_guild.name if target_guild else "Unknown Server"
        logger.info(f"Removed Forwarding Server {server_id_int} for {interaction.guild.name} | {guild_id}")
        await interaction.response.send_message(content=f"The Server {target_name} | {server_id_int} was removed from the forwarding list")
        await client.send_logs(guild_id, "Forwarding-Server", f"{target_name} was removed from the forwarding list")

    @client.tree.command(name="self-logging",description="Enable/Disable Self Logging")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def selfLogging(interaction: discord.Interaction, selflogging: bool=True):
        guild_id = interaction.guild.id
        if not db.check_if_guild_exists(guild_id):
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
            
        db.update_guild_config(guild_id, selfLogging=selflogging)
        logger.info(f"Self-Logging set to {selflogging} for {interaction.guild.name} | {guild_id}")
        await client.send_logs(guild_id, "Self-Logging", f"was set to {selflogging}")
        return await interaction.response.send_message(content=f"Self-Logging Statement is now: {selflogging}")

    @client.tree.command(name="ltl-help",description="What? Where? When? How?")
    async def ltlHelp(interaction: discord.Interaction):
        embed = get_embed("Help",
            "Here you will find the information for the bot.\n\n"
            "**How to Setup?**\n"
            "1. On both Server execute the 'ltl_setup' command and enter your log channel\n"
            "2. For Server A execute the 'forwarding-server' command and enter Server Bs ID\n"
            "a. You will find the ID by right clicking Server B and then click on 'copy Server-ID'\n"
            "b. If you can't see the 'copy Server-ID' then you have to activate developer mode under your settings\n\n"
            "**Which Permission do I need?**\n"
            "For most of the Commands you need the 'Managed Webhooks' permission")
        return await interaction.response.send_message(embed=embed)

    @client.tree.command(name="dev-discord",description="Get an Invite to the Devs Discord server.")
    async def dev_discord(interaction: discord.Interaction):
        return await interaction.response.send_message(content=config.DISCORD_INVITE,ephemeral=True)

    @client.tree.error
    async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            logger.warning(f"{interaction.guild.name} | {interaction.guild.id} | {interaction.user} Missing Permission")
            return await interaction.response.send_message(content="You don't have the right permission.")
        if isinstance(error,app_commands.BotMissingPermissions):
            logger.warning(f"{interaction.guild.name} | {interaction.guild.id} | Missing Channel Access")
            return await interaction.response.send_message(content="The bot executed the command, but is missing permissions (in the provided channel).")
        if isinstance(error,app_commands.CommandAlreadyRegistered):
            logger.warning(error)
            return
        if isinstance(error,app_commands.CommandOnCooldown):
            return await interaction.response.send_message(content=f"This command is on cooldown. Try again in {round(error.retry_after,2)} seconds.",ephemeral=True)
        logger.error(f"{interaction.guild.name} | {interaction.guild.id} | {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(content=f"An error occurred: {error}", ephemeral=True)
            else:
                await interaction.followup.send(content=f"An error occurred: {error}", ephemeral=True)
        except:
            pass  # Ignore if we can't send error message
        raise error

    # Owner-only commands live on the main server; skip them when it isn't configured
    if not main_server:
        return

    @client.tree.command(name="create-embed",description="Send an Embed",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def createEmbed(interaction: discord.Interaction,title: str, description: str):
        embed = get_embed(title,description)
        embed.set_author(name=client.user.display_name,icon_url=client.user.display_avatar)
        return await interaction.response.send_message(embed=embed)
    
    @client.tree.command(name="maintenance",description="Send a notification to the status channel | Bot Owner Only",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def maintenance_command(interaction: discord.Interaction,state: bool,time:int=0):
        global maintenance
        if interaction.user.id != bot_owner:
            return await interaction.response.send_message(content="Only the Bot Owner is allowed to do this",ephemeral=True)
        channel = client.get_channel(main_statusChannel)
        if time == 0:
            maintenance_time = "Unknown"
        else:
            maintenance_time = time
        if state:
            embed = get_embed("Maintenance",f"Bot will go into Maintenance for {maintenance_time} Minutes")
            embed.color = discord.Colour.from_rgb(230,170,42)
        else:
            embed = get_embed("Maintenance",f"Bot back Online after {maintenance_time} Minutes")
            embed.color = discord.Colour.from_rgb(50,200,64)
        maintenance = state
        mode = ""
        if state:
            mode = "**Activated**"
        else:
            mode = "**Deactivated**"
        if channel is None:
            return await interaction.response.send_message(content="Status channel not found, check DISCORD_STATUS_CHANNEL", ephemeral=True)
        await channel.send(embed=embed)
        return await interaction.response.send_message(content=f"Maintenance message was delivered. Maintenance mode is now {mode}")

def run_discord_bot():
    intents = discord.Intents.default()
    intents.bans = True
    intents.emojis = True
    intents.emojis_and_stickers = True
    intents.guild_messages = True
    intents.guild_reactions = True
    intents.guilds = True
    intents.invites = True
    intents.members = True
    intents.message_content = True
    intents.messages = True
    intents.reactions = True
    intents.webhooks = True
    intents.voice_states = True
    client = DiscordBot(command_prefix="/", intents=intents)
    client.run(config.require_token())