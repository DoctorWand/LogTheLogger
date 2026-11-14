"""Log types that can be toggled per server with /log-settings.

Only types the bot actually logs are listed. The database has more columns
(roles, emojis, stickers, webhooks, invites) that no event handler uses yet;
offering them would let admins toggle switches that do nothing.
"""

LOG_TYPES = {
    "memberJoin": "Member joined",
    "memberLeave": "Member left",
    "memberBan": "Member banned",
    "memberUnban": "Member unbanned",
    "memberUpdate": "Member updated (nickname, roles, avatar, name)",
    "messageDelete": "Message deleted",
    "messageBulkDelete": "Messages bulk deleted",
    "messageUpdate": "Message edited, pins changed",
    "messageReactionAdd": "Reaction added",
    "messageReactionRemove": "Reaction removed",
    "messageReactionClear": "Reactions cleared",
    "channelCreate": "Channel created",
    "channelDelete": "Channel deleted",
    "channelUpdate": "Channel updated or moved",
    "voiceChannelJoin": "Voice channel joined",
    "voiceChannelLeave": "Voice channel left",
    "voiceChannelMove": "Voice channel switched",
}
