# Imports
import discord
import json
import time
import datetime

# From x import y
from discord import app_commands
from discord.ext import commands
from discord.ext.tasks import loop


with open("default_config.json",encoding="utf-8") as dc:
    defaultConfig = json.load(dc)


with open("server_config.json",encoding="utf-8") as sc:
    serverConfig = json.load(sc)


with open("D:/BotExtentions/LogTheLogger/ltl-bot.json", encoding="utf-8") as beltl:
    extentionConfig = json.load(beltl)


global server
global statusChannel


# Replacer Vars

server = extentionConfig["discordDevServer"]
# server = defaultConfig["discordServer"]
statusChannel = extentionConfig["discordBotStatus"]
# statusChannel = defaultConfig["discordStatusChannel"]
token = extentionConfig["discordToken"]
# token = defaultConfig["discordToken"]


def load_server_config():
    with open("server_config.json",encoding="utf-8") as sc:
        global serverConfig
        serverConfig = json.load(sc)

def save_server_config():
    with open("server_config.json","w",encoding="utf-8") as nsc:
        json.dump(serverConfig,nsc)


class DiscordBot(commands.Bot):
    async def on_ready(self):
        startup_time_start = time.time()
        bot_commands(self)
        loops(self)
        for guild in self.guilds:
            await self.tree.sync(guild=discord.Object(id=guild.id))
        startup_time_finish = time.time()
        startup_time = round((startup_time_finish - startup_time_start)*1000,2)
        if statusChannel != 0:
            await DiscordBot.send_status(self,"**Bot Online**",f"Startup-Time: {startup_time} Milliseconds.")


    async def send_status(self,status,info):
        channel = self.get_guild(server).get_channel(statusChannel)
        embed = discord.Embed(title=status,description=info,timestamp=datetime.datetime.now())
        await channel.send(embed=embed)

    async def send_logs(self,guild:int,title:str,log:str):
        load_server_config()
        if guild in serverConfig and serverConfig[guild]["logForwarding"]:
            await self.forwarding_logs(serverConfig[guild]["logSendingToServerId"],title,log,guild)
        guild = self.get_guild(guild)
        channel = guild.get_channel(serverConfig[guild]["logChannel"])
        embed = discord.Embed(title=title,description=log,timestamp=datetime.datetime.now())
        await channel.send(embed=embed)

    async def forwarding_logs(self,guild:int,title:str,log:str,fromGuild:int):
        guild = self.get_guild(guild)
        channel = guild.get_channel(serverConfig[guild]["logChannel"])
        embed = discord.Embed(title=title,description=log,timestamp=datetime.datetime.now())
        embed.add_field(name="From Server:",value=f"{self.get_guild(guild).name} | {guild}")
        await channel.send(embed=embed)


def loops(client):
    @loop(hours=24)
    async def check_service():
        if server != 1345495816202227752:
            return
        if defaultConfig["discordInvite"] != "https://discord.gg/mpgbu3M5Yy":
            return
        
    check_service.start()
        


def bot_commands(client):
    @client.tree.command(name="setup",description="Initial Setup.",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True) #discord.Permissions.manage_webhooks
    async def setup(interaction: discord.Interaction):
        await interaction.response.send_message(content=interaction.guild.id,ephemeral=True)

    @client.tree.command(name="forwarding",description="Enable/Disable Log Forwarding",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwarding(interaction: discord.Interaction, statement: bool):
        guild = interaction.guild_id
        if guild not in serverConfig:
            return await interaction.response.send_message(content="The /setup command wasn't executet yet!")
        load_server_config()
        serverConfig[guild]["logForwarding"] = statement
        save_server_config()
        await interaction.response.send_message(content=f"Forwarding Statement is now: {statement}")

    @client.tree.command(name="forwarding-server",description="The Server you want to get it forwarded",guilds=list(client.guilds))
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def forwardingServer(interaction: discord.Interaction, server: int, channel: int):
        guild = interaction.guild_id
        if guild not in serverConfig:
            return await interaction.response.send_message(content="The /setup command wasn't executet yet!")
        load_server_config()
        serverConfig[guild]["logSendingToServerId"] = server
        serverConfig[guild]["logSendingToServerChannel"] = channel
        save_server_config()
    
    @client.tree.command(name="dev-discord",description="Get an Invite to the Devs Discord server.",guilds=list(client.guilds))
    async def dev_discord(interaction: discord.Interaction):
        await interaction.response.send_message(content=defaultConfig["discordInvite"],ephemeral=True)

    @client.tree.error
    async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            return await interaction.response.send_message(content="You don't have the permission.")
        else:
            await interaction.response.send_message(content=error)
            raise error


def run_discord_bot():
    # Bot Essential Vars
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True
    client = DiscordBot(command_prefix="!",intents=intents,server=server,statusChannel=statusChannel)

    client.run(token)


run_discord_bot()