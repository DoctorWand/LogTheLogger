import sqlite3
import os
import json

import config

class DatabaseHandler:
    def __init__(self):
        self.DB_PATH = config.DATABASE_PATH
        db_dir = os.path.dirname(self.DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.initialize_db()

    def initialize_db(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guildID INTEGER PRIMARY KEY,
                guildName TEXT,
                logChannel INTEGER,
                logForwarding BOOLEAN,
                onlyForwarding BOOLEAN,
                selfLogging BOOLEAN,
                logSendingToServerId TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_settings (
                guildID INTEGER PRIMARY KEY,
                memberJoin BOOLEAN,
                memberLeave BOOLEAN,
                memberBan BOOLEAN,
                memberUnban BOOLEAN,
                memberUpdate BOOLEAN,
                messageDelete BOOLEAN,
                messageBulkDelete BOOLEAN,
                messageUpdate BOOLEAN,
                messageReactionAdd BOOLEAN,
                messageReactionRemove BOOLEAN,
                messageReactionClear BOOLEAN,
                channelCreate BOOLEAN,
                channelDelete BOOLEAN,
                channelUpdate BOOLEAN,
                roleCreate BOOLEAN,
                roleDelete BOOLEAN,
                roleUpdate BOOLEAN,
                emojiCreate BOOLEAN,
                emojiDelete BOOLEAN,
                emojiUpdate BOOLEAN,
                stickersCreate BOOLEAN,
                stickersDelete BOOLEAN,
                stickersUpdate BOOLEAN,
                webhooksUpdate BOOLEAN,
                invitesCreate BOOLEAN,
                invitesDelete BOOLEAN,
                voiceChannelJoin BOOLEAN,
                voiceChannelLeave BOOLEAN,
                voiceChannelMove BOOLEAN
            )
        ''')
        
        conn.commit()
        conn.close()

    def connect_db(self):
        """Create database connection"""
        return sqlite3.connect(self.DB_PATH)

    def init_new_guild(self, guild_id: int, guild_name: str) -> None:
        """Initialize a new guild with default settings"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO guilds (guildID, guildName, logChannel, logForwarding, onlyForwarding, selfLogging, logSendingToServerId)
            VALUES (?, ?, 0, 1, 0, 0, '[]')
        ''', (guild_id, guild_name))
        
        # Fixed: Now providing 30 values for 30 columns (including guildID + 29 boolean settings)
        cursor.execute('''
            INSERT OR IGNORE INTO log_settings (
                guildID, memberJoin, memberLeave, memberBan, memberUnban, memberUpdate,
                messageDelete, messageBulkDelete, messageUpdate, messageReactionAdd, messageReactionRemove,
                messageReactionClear, channelCreate, channelDelete, channelUpdate, roleCreate,
                roleDelete, roleUpdate, emojiCreate, emojiDelete, emojiUpdate,
                stickersCreate, stickersDelete, stickersUpdate, webhooksUpdate,
                invitesCreate, invitesDelete, voiceChannelJoin, voiceChannelLeave, voiceChannelMove
            )
            VALUES (?, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
        ''', (guild_id,))

        conn.commit()
        conn.close()

    def remove_guild(self, guild_id: int) -> None:
        """Remove a guild from the database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM guilds WHERE guildID = ?', (guild_id,))
        cursor.execute('DELETE FROM log_settings WHERE guildID = ?', (guild_id,))
        
        conn.commit()
        conn.close()

    def get_guild_config(self, guild_id: int) -> dict:
        """Get guild configuration"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM guilds WHERE guildID = ?', (guild_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                "guildID": result[0],
                "guildName": result[1],
                "logChannel": result[2],
                "logForwarding": bool(result[3]),
                "onlyForwarding": bool(result[4]),
                "selfLogging": bool(result[5]),
                "logSendingToServerId": json.loads(result[6])
            }
        else:
            return None

    def update_guild_config(self, guild_id: int, **kwargs) -> None:
        """Update guild configuration with flexible parameters"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key == "logSendingToServerId":
                value = json.dumps(value)
            fields.append(f"{key} = ?")
            values.append(value)
        
        values.append(guild_id)
        sql = f"UPDATE guilds SET {', '.join(fields)} WHERE guildID = ?"
        
        cursor.execute(sql, values)
        conn.commit()
        conn.close()

    def get_log_settings(self, guild_id: int) -> dict:
        """Get log settings for a guild"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM log_settings WHERE guildID = ?', (guild_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                "guildID": result[0],
                "memberJoin": bool(result[1]),
                "memberLeave": bool(result[2]),
                "memberBan": bool(result[3]),
                "memberUnban": bool(result[4]),
                "memberUpdate": bool(result[5]),
                "messageDelete": bool(result[6]),
                "messageBulkDelete": bool(result[7]),
                "messageUpdate": bool(result[8]),
                "messageReactionAdd": bool(result[9]),
                "messageReactionRemove": bool(result[10]),
                "messageReactionClear": bool(result[11]),
                "channelCreate": bool(result[12]),
                "channelDelete": bool(result[13]),
                "channelUpdate": bool(result[14]),
                "roleCreate": bool(result[15]),
                "roleDelete": bool(result[16]),
                "roleUpdate": bool(result[17]),
                "emojiCreate": bool(result[18]),
                "emojiDelete": bool(result[19]),
                "emojiUpdate": bool(result[20]),
                "stickersCreate": bool(result[21]),
                "stickersDelete": bool(result[22]),
                "stickersUpdate": bool(result[23]),
                "webhooksUpdate": bool(result[24]),
                "invitesCreate": bool(result[25]),
                "invitesDelete": bool(result[26]),
                "voiceChannelJoin": bool(result[27]),
                "voiceChannelLeave": bool(result[28]),
                "voiceChannelMove": bool(result[29])
            }
        else:
            return None
        
    def update_log_settings(self, guild_id: int, **kwargs) -> None:
        """Update log settings for a guild"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        values.append(guild_id)
        sql = f"UPDATE log_settings SET {', '.join(fields)} WHERE guildID = ?"
        
        cursor.execute(sql, values)
        conn.commit()
        conn.close()

    def check_if_guild_exists(self, guild_id: int) -> bool:
        """Check if a guild exists in the database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM guilds WHERE guildID = ?', (guild_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists



db = DatabaseHandler() # Create a global instance for backward compatibility