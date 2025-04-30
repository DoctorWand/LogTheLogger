# Imports
import discord
import json
import time
import datetime
import os
import re
import logging

# From x import y
from discord import app_commands
from discord.ext import commands
from discord.ext.tasks import loop
from logging.handlers import TimedRotatingFileHandler

# Setup file logging
LOG_DIR = "Logs"
BASE_LOG_NAME = "JASTBI-LogTheLogger"
RETENTION_DAYS = 30
os.makedirs(LOG_DIR,exist_ok=True)
today_str = datetime.datetime.now().strftime("%d.%m.%Y")
log_name = f"{BASE_LOG_NAME}-{today_str}.log"
log_path = os.path.join(LOG_DIR,log_name)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = TimedRotatingFileHandler(filename=log_path,when="midnight",interval=1,backupCount=0,encoding="utf-8",delay=False)
    formatter = logging.Formatter(datefmt='%d.%m.%Y %H:%M:%S',fmt='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Clear Old Logs
def clean_old_logs(directory, base_name, retention_days):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    pattern = re.compile(rf"{re.escape(base_name)}-(\d{{2}}.\d{{2}}.\d{{4}})\.log")

    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            file_date = datetime.datetime.strptime(match.group(1),"%d.%m.%Y")
            if file_date < cutoff:
                full_path = os.path.join(directory,filename)
                os.remove(full_path)
                print(f"Deleted old log: {full_path}")
                logger.info(f"Deleted old log: {full_path}")


global main_server
global main_statusChannel
global token
global serverConfig

# Initial load of configs
with open("default_config.json",encoding="utf-8") as dc:
    defaultConfig = json.load(dc)

with open("server_config.json",encoding="utf-8") as sc:
    serverConfig = json.load(sc)

if os.path.exists("D:/BotExtentions/LogTheLogger/ltl-bot.json"):
    with open("D:/BotExtentions/LogTheLogger/ltl-bot.json", encoding="utf-8") as beltl:
        extentionConfig = json.load(beltl)
    
    main_server = extentionConfig["discordDevServer"]
    main_statusChannel = extentionConfig["discordBotStatus"]
    token = extentionConfig["discordToken"]
    bot_owner = extentionConfig["botOwner"]
else:
    main_server = defaultConfig["discordServer"]
    main_statusChannel = defaultConfig["discordStatusChannel"]
    token = defaultConfig["discordToken"]
    bot_owner = defaultConfig["botOwner"]


# Save n' Load Server-Config
def load_server_config():
    with open("server_config.json",encoding="utf-8") as sc:
        global serverConfig
        serverConfig = json.load(sc)

def save_server_config():
    with open("server_config.json","w",encoding="utf-8") as nsc:
        json.dump(serverConfig,nsc)

# Getting base embed
def get_embed(title:str,description:str) -> discord.Embed:
    embed = discord.Embed(title=title,description=description,timestamp=datetime.datetime.now())
    return embed

# The Magic
class DiscordBot(commands.Bot):
    async def on_ready(self):
        startup_time_start = time.time()
        bot_commands(self)
        loops(self)
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=discord.Object(id=guild.id))
                logger.info(f"Synced {guild.name} successfully")
            except Exception as e:
                logger.error(f"{guild.name} | Error: {e}")
        startup_time_finish = time.time()
        startup_time = round((startup_time_finish - startup_time_start)*1000,2)
        logger.info(f"Bot startup successfully | Startup-Time: {startup_time} Milliseconds.")
        if main_statusChannel != 0:
            return await DiscordBot.send_status(self,"**Bot Online**",f"Startup-Time: {startup_time} Milliseconds.")

    
    async def on_message(self,message):
        guild = str(message.guild.id)
        if guild not in serverConfig:
            return
        if serverConfig[guild]["logForwarding"] == False:
            return
        if message.channel.id == serverConfig[guild]["logChannel"]:
            for embed in message.embeds:
                for guild in serverConfig[guild]["logSendingToServerId"]:
                    await self.forwarding_embeds(guild,embed,message.guild.id)


    async def on_guild_join(self,guild):
        logger.info(f"Start Syncing new Guild {guild.name} ...")
        try:
            await self.tree.sync(guild=guild)
            logger.info(f"Synced new Guild {guild.name} successfully")
        except Exception as e:
            logger.error(f"Sync failed for Guild {guild.name} , Error: {e}")


    async def send_status(self,status,info):
        channel = self.get_guild(main_server).get_channel(main_statusChannel)
        embed = get_embed(status,info)
        await channel.send(embed=embed)

    async def send_logs(self,guild:int,title:str,log:str):
        load_server_config()
        guild = str(guild)
        if serverConfig[guild]["onlyForwarding"]:
            return
        guild = self.get_guild(int(guild))
        channel = guild.get_channel(serverConfig[str(guild.id)]["logChannel"])
        embed = get_embed(title,log)
        embed.set_author(name=guild.name,icon_url=guild.icon)
        return await channel.send(embed=embed)

    async def forwarding_embeds(self,guild:int,embed:discord.Embed,fromGuild:int):
        guild = self.get_guild(guild)
        fromGuild = self.get_guild(fromGuild)
        channel = guild.get_channel(serverConfig[str(guild.id)]["logChannel"])
        embed.set_author(name=fromGuild.name,icon_url=fromGuild.icon)
        embed.set_footer(text=f"From Server: {fromGuild.name}")
        return await channel.send(embed=embed)

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
        logger.info(f"Checked for Old Logs - {datetime.datetime.now().strftime("%d.%m.%Y | %H:%M:%S")}")

    check_service.start()
    clear_old_logs.start()
        
# Slash Commands
def bot_commands(client):
    @client.tree.command(name="setup",description="Initial Setup.",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True) #discord.Permissions.manage_webhooks
    @app_commands.describe(logchannel = "The Channel where logs are getting send to.")
    async def setup(interaction: discord.Interaction, logchannel: discord.TextChannel):
        guild = str(interaction.guild_id)
        if guild in serverConfig:
            return await interaction.response.send_message(content="Setup was already executed")
        load_server_config()
        serverConfig[guild] = {}
        serverConfig[guild]["logChannel"] = logchannel.id
        serverConfig[guild]["logForwarding"] = True
        serverConfig[guild]["onlyForwarding"] = False
        serverConfig[guild]["logSendingToServerId"] = []
        save_server_config()
        await client.send_logs(int(guild),"Setup","completed successfully")
        return await interaction.response.send_message(content=f"Setup was completed for ***{interaction.guild}*** | ***{guild}***")

    @client.tree.command(name="forwarding",description="Enable/Disable Log Forwarding",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwarding(interaction: discord.Interaction, forwarding: bool=True):
        guild = str(interaction.guild_id)
        if guild not in serverConfig:
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
        load_server_config()
        serverConfig[guild]["logForwarding"] = forwarding
        #serverConfig[guild]["onlyForwarding"] = onlyforwarding #activate when self logging is implementet
        save_server_config()
        await client.send_logs(int(guild),"Forwarding",f"Statement is now: {forwarding}")
        return await interaction.response.send_message(content=f"Forwarding Statement is now: {forwarding}")

    @client.tree.command(name="forwarding-server",description="The Server you want to get it forwarded",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwardingServer(interaction: discord.Interaction, server_id: str):
        if server_id.isdigit() == False:
            return await interaction.response.send_message(content="Please enter a server id and not a server name")
        guild = str(interaction.guild.id)
        load_server_config()
        if guild not in serverConfig:
            return await interaction.response.send_message(content="The /setup command wasn't executed yet!")
        if server_id not in serverConfig:
            return await interaction.response.send_message(content="The /setup command wasn't executed on the other server yet!")
        server_id = int(server_id)
        if server_id in serverConfig[guild]["logSendingToServerId"]:
            return await interaction.response.send_message(content="Server is already in forwarding list")
        if not serverConfig[guild]["logSendingToServerId"]:
            serverConfig[guild]["logSendingToServerId"] = [server_id]
        else:
            serverConfig[guild]["logSendingToServerId"] = serverConfig[guild]["logSendingToServerId"].append(server_id)
        save_server_config()
        await client.send_logs(guild,"Forwarding-Server",f"{client.get_guild(server_id).name} was added to the forwarding list")
        return await interaction.response.send_message(content=f"The Server {client.get_guild(server_id).name} | {server_id} was added successfully")
    
    @client.tree.command(name="delete-forwarding-server",description="Delets a Server from the forwarding list",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def deleteForwardingServer(interaction: discord.Interaction, server_id: str):
        if server_id.isdigit() == False:
            return await interaction.response.send_message(content="Please enter a server id and not a server name")
        guild = str(interaction.guild.id)
        server_id = int(server_id)
        if server_id not in serverConfig[guild]["logSendingToServerId"]:
            return await interaction.response.send_message(content="The server id is not in the database for your server")
        serverConfig[guild]["logSendingToServerId"].remove(server_id)
        await client.send_logs(guild,"Forwarding-Server",f"{client.get_guild(server_id).name} was removed to the forwarding list")
        return await interaction.response.send_message(content=f"The Server {client.get_guild(server_id).name} | {server_id} was removed from the forwarding list")

    @client.tree.command(name="dev-discord",description="Get an Invite to the Devs Discord server.",guilds=list(client.guilds))
    async def dev_discord(interaction: discord.Interaction):
        return await interaction.response.send_message(content=defaultConfig["discordInvite"],ephemeral=True)

    @client.tree.command(name="create-embed",description="Send an Embed",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def createEmbed(interaction: discord.Interaction,title: str, description: str):
        embed = get_embed(title,description)
        embed.set_author(name=client.user.display_name,icon_url=client.user.display_avatar)
        return await interaction.response.send_message(embed=embed)
    
    @client.tree.command(name="maintenance",description="Send a notification to the status channel",guild=discord.Object(id=main_server))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def maintenance(interaction: discord.Interaction,state: bool,time:int=0):
        if interaction.user.id != bot_owner:
            return await interaction.response.send_message(content="Only the Bot Owner is allowed todo this",ephemeral=True)
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
        await channel.send(embed=embed)
        return await interaction.response.send_message(content="Maintenance message was delivered")

    @client.tree.error
    async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            logger.warning(f"{interaction.guild.name} | {interaction.guild.id} | {interaction.user} Missing Permission")
            return await interaction.response.send_message(content="You don't have the right permission.")
        else:
            logger.error(f"{interaction.guild.name} | {interaction.guild.id} | {error}")
            await interaction.response.send_message(content=error)
            raise error


def run_discord_bot():
    # Bot Essential Vars
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True
    intents.guilds = True
    client = DiscordBot(command_prefix="!",intents=intents,server=main_server,statusChannel=main_statusChannel)

    client.run(token)