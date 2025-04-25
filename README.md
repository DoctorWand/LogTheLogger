# LogTheLogger
LogTheLogger is an Open Source Discord Bot for Logging onto another Discord Server
Currently Work-In-Progress

## Discord Server
https://discord.gg/mpgbu3M5Yy

## How to setup
1. Invite the Bot on both servers
2. Execute on both servers the /setup command
3. On the main server execute the /forwarding-server command and enter the seconds server id
    a. with executing this command you should start seeing the logs from server A on server B

## Running your own instance
1. Fill out the default_config.json
    a. "discordToken" -> Your Discord bot token
    b. "discordServer" -> Your server id
    c. "discordStatusChannel" -> Your status server (if you don't have one, just leave the 0)
2. Start the main.py file
