# Imports
import discord
import json
import time
import datetime
import os
import re
import logging
import pytz

# From x import y
from discord import app_commands
from discord.ext import commands
from discord.ext.tasks import loop
from logging.handlers import TimedRotatingFileHandler
from db_handler import db

# Setup file logging
if not os.path.exists("F:/DiscordBotsData/LogTheLogger/Logs"):
    LOG_DIR = "Logs"
else:
    LOG_DIR = "F:/DiscordBotsData/LogTheLogger/Logs"
BASE_LOG_NAME = "JASTBI-LogTheLogger"
RETENTION_DAYS = 8
TIMEZONE = "Europe/Berlin"

os.makedirs(LOG_DIR,exist_ok=True)
today_str = datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime("%d.%m.%Y")
log_name = f"{BASE_LOG_NAME}.{today_str}.log"
log_path = os.path.join(LOG_DIR,log_name)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR,BASE_LOG_NAME),
        when="midnight",
        interval=1,
        backupCount=RETENTION_DAYS,
        encoding="utf-8",
        utc=False
    )
    handler.suffix = "%d.%m.%Y.log"
    formatter = logging.Formatter(datefmt='%d.%m.%Y %H:%M:%S',fmt='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
                    
                    print(f"Deleted old log: {full_path}")
                    logger.info(f"Deleted old log: {full_path}")
                    logs_deleted = True
            except Exception as e:
                print(f"Error - Log {filename} couldn't be deleted, Error: {e}")
                logger.warning(f"Error - Log {filename} couldn't be deleted, Error: {e}")
                raise e
    
    if not logs_deleted:
        print(f"No old logs found - {datetime.datetime.now()}")
        logger.info("No old logs found")

global main_server
global main_statusChannel
global token

# Initial load of configs
with open("default_config.json",encoding="utf-8") as dc:
    defaultConfig = json.load(dc)

if os.path.exists("E:/BotExtentions/LogTheLogger/ltl-bot.json"):
    with open("E:/BotExtentions/LogTheLogger/ltl-bot.json", encoding="utf-8") as beltl:
        extentionConfig = json.load(beltl)
    
    main_server = extentionConfig["discordDevServer"]
    main_statusChannel = extentionConfig["discordBotStatus"]
    token = extentionConfig["discordToken"]
    bot_owner = extentionConfig["botOwner"]
    maintenance = extentionConfig["maintenanceMode"]
else:
    main_server = defaultConfig["discordServer"]
    main_statusChannel = defaultConfig["discordStatusChannel"]
    token = defaultConfig["discordToken"]
    bot_owner = defaultConfig["botOwner"]
    maintenance = defaultConfig["maintenanceMode"]

# Getting base embed
def get_embed(title:str,description:str) -> discord.Embed:
    embed = discord.Embed(title=title,description=description,timestamp=datetime.datetime.now())
    return embed

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
    async def on_ready(self):
        print(f'We have logged in as {self.user} | ID: {self.user.id}')
        startup_time_start = time.time()
        try:
            bot_commands(self)
        except Exception as e:
            logger.error(f"Setup Command Error: {e}")
            raise e
        logging.info("~Start Syncing Guilds~")
        for guild in self.guilds:
            if guild.id == 846869213732929536:
                self.tree.copy_global_to(guild=discord.Object(id=846869213732929536))
                await self.tree.sync(guild=discord.Object(id=846869213732929536))
        try:
            await self.tree.sync()
            logger.info(f"Synced Commands successfully")
        except Exception as e:
            logger.error(f"Sync Commands | Error: {e}")
            raise e
        logger.info("~End Syncing Guilds~")
        loops(self)
        startup_time_finish = time.time()
        startup_time = round((startup_time_finish - startup_time_start)*1000,2)
        logger.info(f"Bot startup successfully | Startup-Time: {startup_time} Milliseconds.")
        if main_statusChannel != 0 and not maintenance:
            return await DiscordBot.send_status(self,"**Bot Online**",f"Startup-Time: {startup_time} Milliseconds.")

    async def on_message(self,message):
        if message.author == self.user:
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
        self.wait_until_ready()
        logger.info(f"~~~Start Syncing new Guild: [{guild.name}] ...~~~")
        try:
            await self.tree.sync(guild=discord.Object(id=guild.id))
            logger.info(f"~~~Synced new Guild: [{guild.name}] successfully~~~")
        except Exception as e:
            logger.error(f"~~~Sync failed for Guild: [{guild.name}] , Error: {e}~~~")
            raise e
        return

    async def on_guild_leave(self, guild):
        if db.check_if_guild_exists(guild.id):
            db.remove_guild(guild.id)
            logger.info(f"Left Guild | {guild.id} | Removed from Database")
        return

    async def send_status(self,status,info):
        channel = self.get_guild(main_server).get_channel(main_statusChannel)
        embed = get_embed(status,info)
        return await channel.send(embed=embed)

    async def send_logs(self, guild_id: int, title: str, log: str):
        guild = self.get_guild(guild_id)
        guild_config = db.get_guild_config(guild_id)
        channel = guild.get_channel(guild_config["logChannel"])
        embed = get_embed(title, log)
        embed.set_author(name=guild.name, icon_url=guild.icon)
        
        if not guild_config["onlyForwarding"]:
            await channel.send(embed=embed)
            
        for forwarding_guild in guild_config["logSendingToServerId"]:
            await self.forwarding_embeds(forwarding_guild, embed, guild_id)
        return

    async def forwarding_embeds(self, guild_id: int, embed: discord.Embed, from_guild_id: int):
        if not db.check_if_guild_exists(guild_id):
            return
            
        guild = self.get_guild(guild_id)
        from_guild = self.get_guild(from_guild_id)
        guild_config = db.get_guild_config(guild_id)
        channel = guild.get_channel(guild_config["logChannel"])
        embed.set_author(name=from_guild.name, icon_url=from_guild.icon)
        embed.set_footer(text=f"From Server: {from_guild.name}")
        return await channel.send(embed=embed)

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
        member = guild.get_member(payload.user_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        emoji = str(payload.emoji)
        if len(emoji) > 100:
            emoji = emoji[:97] + "..."
        
        log = f"**User:** {member} | {member.id}\n**Channel:** {channel.mention} | {channel.id}\n**Message ID:** {message.id}\n**Emoji:** {emoji}"
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
        member = guild.get_member(payload.user_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        emoji = str(payload.emoji)
        if len(emoji) > 100:
            emoji = emoji[:97] + "..."
        
        log = f"**User:** {member} | {member.id}\n**Channel:** {channel.mention} | {channel.id}\n**Message ID:** {message.id}\n**Emoji:** {emoji}"
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
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        log = f"**Channel:** {channel.mention} | {channel.id}\n**Message ID:** {message.id}"
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
        
        log = f"**User ID:** {payload.user_id}\n**Member Count:** {guild.member_count}"
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
            before_roles = ', '.join([role.name for role in before.roles if role.name != "@everyone"])
            after_roles = ', '.join([role.name for role in after.roles if role.name != "@everyone"])
            changes.append(f"**Roles:** {before_roles} -> {after_roles}")
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
        message_id = payload.message_id
        cached_message = payload.cached_message.content if payload.cached_message else "Content not cached"
        
        log = f"**Channel:** {channel.mention}\n**Message:** {cached_message}\n**Message ID:** {message_id}"
        await self.send_logs(guild_id, "Message Delete", log)
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
        message_ids = payload.message_ids
        
        log = f"**Channel:** {channel.mention} | {channel.id}\n**Message IDs:** {', '.join(map(str, message_ids))}"
        await self.send_logs(guild_id, "Bulk Message Delete", log)
        return

    async def on_raw_message_edit(self, payload):
        if payload.data.get("author", {}).get("id") == str(self.user.id):
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
        channel = guild.get_channel(payload.channel_id)
        
        before_content = payload.cached_message.content if payload.cached_message else "Content not cached"
        after_content = payload.data.get("content", "")

        if before_content == after_content:
            return

        author_id = payload.data.get("author", {}).get("id")
        author = guild.get_member(int(author_id)) if author_id else "Unknown User"

        log = f"**User:** {author}\n**Channel:** {channel.mention}\n**Message ID:** {payload.message_id}\n**Before:** {before_content}\n**After:** {after_content}"
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

# Automation Tasks
def loops(client):
    @loop(hours=24)
    async def check_service():
        if main_server == 1345495816202227752 or defaultConfig["discordInvite"] != "https://discord.gg/mpgbu3M5Yy":
            return
        return
    
    @loop(hours=12)
    async def clear_old_logs():
        clean_old_logs(LOG_DIR,BASE_LOG_NAME,RETENTION_DAYS)
        logger.info(f"Checked for Old Logs - {datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m.%Y | %H:%M:%S')}")

    check_service.start()
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
        await client.send_logs(guild_id, "Setup", "completed successfully")
        return await interaction.response.send_message(content=f"Setup was completed for ***{interaction.guild}*** | ***{guild_id}***")

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
            
        guild_config = db.get_guild_config(guild_id)
        current_list = guild_config["logSendingToServerId"]
        
        if server_id_int in current_list:
            return await interaction.response.send_message(content="Server is already in forwarding list")
            
        current_list.append(server_id_int)
        db.update_guild_config(guild_id, logSendingToServerId=current_list)
        
        logger.info(f"Added Forwarding Server {server_id_int} for {interaction.guild.name} | {guild_id}")
        await client.send_logs(guild_id, "Forwarding-Server", f"{client.get_guild(server_id_int).name} was added to the forwarding list")
        return await interaction.response.send_message(content=f"The Server {client.get_guild(server_id_int).name} | {server_id_int} was added successfully")
    
    @client.tree.command(name="delete-forwarding-server",description="Deletes a Server from the forwarding list")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def deleteForwardingServer(interaction: discord.Interaction, server_id: str):
        if not server_id.isdigit():
            return await interaction.response.send_message(content="Please enter a server-id and not a server-name")
            
        guild_id = interaction.guild.id
        server_id_int = int(server_id)
        
        guild_config = db.get_guild_config(guild_id)
        current_list = guild_config["logSendingToServerId"]
        
        if server_id_int not in current_list:
            return await interaction.response.send_message(content="The server-id you provided is not in the database for your server")
            
        current_list.remove(server_id_int)
        db.update_guild_config(guild_id, logSendingToServerId=current_list)
        
        logger.info(f"Removed Forwarding Server {server_id_int} for {interaction.guild.name} | {guild_id}")
        await client.send_logs(guild_id, "Forwarding-Server", f"{client.get_guild(server_id_int).name} was removed from the forwarding list")
        return await interaction.response.send_message(content=f"The Server {client.get_guild(server_id_int).name} | {server_id_int} was removed from the forwarding list")

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
        return await interaction.response.send_message(content=defaultConfig["discordInvite"],ephemeral=True)

    @client.tree.command(name="create-embed",description="Send an Embed",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def createEmbed(interaction: discord.Interaction,title: str, description: str):
        embed = get_embed(title,description)
        embed.set_author(name=client.user.display_name,icon_url=client.user.display_avatar)
        return await interaction.response.send_message(embed=embed)
    
    @client.tree.command(name="maintenance",description="Send a notification to the status channel | Bot Owner Only",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def maintenance(interaction: discord.Interaction,state: bool,time:int=0):
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
            if os.path.exists("E:/BotExtentions/LogTheLogger/ltl-bot.json"):
                extentionConfig["maintenanceMode"] = state
                with open("E:/BotExtentions/LogTheLogger/ltl-bot.json","w",encoding="utf-8") as nsc:
                    json.dump(extentionConfig,nsc)
            else:
                defaultConfig["maintenanceMode"] = state
                with open("default_config.json","w",encoding="utf-8") as nsc:
                    json.dump(defaultConfig,nsc)
        else:
            embed = get_embed("Maintenance",f"Bot back Online after {maintenance_time} Minutes")
            embed.color = discord.Colour.from_rgb(50,200,64)
            if os.path.exists("E:/BotExtentions/LogTheLogger/ltl-bot.json"):
                extentionConfig["maintenanceMode"] = state
                with open("E:/BotExtentions/LogTheLogger/ltl-bot.json","w",encoding="utf-8") as nsc:
                    json.dump(extentionConfig,nsc)
            else:
                defaultConfig["maintenanceMode"] = state
                with open("default_config.json","w",encoding="utf-8") as nsc:
                    json.dump(defaultConfig,nsc)
        mode = ""
        if state:
            mode = "**Activated**"
        else:
            mode = "**Deactivated**"
        await channel.send(embed=embed)
        return await interaction.response.send_message(content=f"Maintenance message was delivered. Maintenance mode is now {mode}")

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


def run_discord_bot():
    intents = discord.Intents.default()
    intents.bans = True
    intents.emojis = True
    intents.emojis_and_stickers = True
    intents.guild_messages = True
    intents.guild_reactions = True
    intents.guilds = True
    intents.integrations = True
    intents.invites = True
    intents.members = True
    intents.message_content = True
    intents.messages = True
    intents.reactions = True
    intents.typing = True
    intents.webhooks = True
    intents.voice_states = True
    client = DiscordBot(command_prefix="/", intents=intents)
    client.run(token)