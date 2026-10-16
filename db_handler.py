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

        # Forwarding needs the target's consent: a link is 'pending' until the
        # target server accepts it, and only 'approved' links receive logs.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forwarding_links (
                sourceGuildID INTEGER NOT NULL,
                targetGuildID INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved')),
                createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (sourceGuildID, targetGuildID)
            )
        ''')

        self._migrate_legacy_forwarding(cursor)

        conn.commit()
        conn.close()

    def _migrate_legacy_forwarding(self, cursor) -> None:
        """Move forwarding targets from guilds.logSendingToServerId (JSON list) into
        forwarding_links. Existing links are kept as approved so running setups don't
        break; the column is emptied afterwards so this runs only once per entry."""
        cursor.execute("SELECT guildID, logSendingToServerId FROM guilds WHERE logSendingToServerId NOT IN ('', '[]')")
        for guild_id, raw_targets in cursor.fetchall():
            try:
                targets = json.loads(raw_targets)
            except (TypeError, ValueError):
                targets = []
            for target_id in targets:
                cursor.execute('''
                    INSERT OR IGNORE INTO forwarding_links (sourceGuildID, targetGuildID, status)
                    VALUES (?, ?, 'approved')
                ''', (guild_id, int(target_id)))
            cursor.execute("UPDATE guilds SET logSendingToServerId = '[]' WHERE guildID = ?", (guild_id,))

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
        cursor.execute('DELETE FROM forwarding_links WHERE sourceGuildID = ? OR targetGuildID = ?', (guild_id, guild_id))

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

    def get_forwarding_link(self, source_guild_id: int, target_guild_id: int) -> str | None:
        """Return the link status ('pending' / 'approved') or None if there is no link"""
        conn = self.connect_db()
        cursor = conn.cursor()

        cursor.execute('SELECT status FROM forwarding_links WHERE sourceGuildID = ? AND targetGuildID = ?', (source_guild_id, target_guild_id))
        result = cursor.fetchone()

        conn.close()
        return result[0] if result else None

    def set_forwarding_link(self, source_guild_id: int, target_guild_id: int, status: str) -> None:
        """Create or update a forwarding link"""
        conn = self.connect_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO forwarding_links (sourceGuildID, targetGuildID, status)
            VALUES (?, ?, ?)
            ON CONFLICT (sourceGuildID, targetGuildID) DO UPDATE SET status = excluded.status
        ''', (source_guild_id, target_guild_id, status))

        conn.commit()
        conn.close()

    def remove_forwarding_link(self, source_guild_id: int, target_guild_id: int) -> bool:
        """Delete a forwarding link, returns True if one existed"""
        conn = self.connect_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM forwarding_links WHERE sourceGuildID = ? AND targetGuildID = ?', (source_guild_id, target_guild_id))
        removed = cursor.rowcount > 0

        conn.commit()
        conn.close()
        return removed

    def get_forwarding_targets(self, source_guild_id: int) -> list[int]:
        """Approved targets this guild forwards its logs to"""
        conn = self.connect_db()
        cursor = conn.cursor()

        cursor.execute("SELECT targetGuildID FROM forwarding_links WHERE sourceGuildID = ? AND status = 'approved'", (source_guild_id,))
        targets = [row[0] for row in cursor.fetchall()]

        conn.close()
        return targets

    def list_forwarding_links(self, guild_id: int) -> dict:
        """All outgoing and incoming links of a guild with their status"""
        conn = self.connect_db()
        cursor = conn.cursor()

        cursor.execute('SELECT targetGuildID, status FROM forwarding_links WHERE sourceGuildID = ?', (guild_id,))
        outgoing = cursor.fetchall()
        cursor.execute('SELECT sourceGuildID, status FROM forwarding_links WHERE targetGuildID = ?', (guild_id,))
        incoming = cursor.fetchall()

        conn.close()
        return {"outgoing": outgoing, "incoming": incoming}



db =DatabaseHandler() # Create a global instance for backward compatibility