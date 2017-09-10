"""Module for PugVoice cog."""
import re
import discord
from r6pugs import Pug, PugMatch

_HEADER_CHANNEL = "----------------------"
_LOBBY_NAME = "\N{Dog Face} Pug {0} - Lobby"
_TEAM_CHANNEL_NAME = "\N{Dog} Pug {0} {1}"
_BLUE = "\N{Large Blue Diamond}"
_ORANGE = "\N{Large Orange Diamond}"

# decorators
def pug_has_voice_channels(func):
    """Decorator which makes sure the function only runs if
    there are voice channels for the pug being passed in.
    """
    async def _decorated(cog, *args, **kwargs):
        pug = next((arg for arg in args if isinstance(arg, Pug)), None)
        if pug is None or pug not in cog.channels:
            return
        await func(cog, *args, **kwargs)
    return _decorated

def match_has_voice_channels(func):
    """Decorator which gets the pug for the match and passes it in,
    if there are voice channels for it.
    """
    async def _decorated(cog, *args, **kwargs):
        match = next((arg for arg in args if isinstance(arg, PugMatch)), None)
        if match is None:
            return
        args = list(args)
        args.remove(match)
        pug = match.ctx.cog.get_pug(match.ctx.channel)
        if pug is None or pug not in cog.channels:
            return
        await func(cog, match, pug, *args, **kwargs)
    return _decorated

class PugVoice:
    """Cog to manage voice channels for PUGs."""

    def __init__(self):
        self.channels = {}

    async def on_pug_start(self, pug: Pug):
        """Fires when a PUG starts and creates new voice channels for it."""
        pug_n = re.findall(r'\d+', pug.ctx.channel.name)
        if not pug_n:
            return
        pug_n = int(pug_n.pop())
        guild = pug.ctx.guild
        bot_settings = pug.ctx.bot.db.guild(guild)
        mod_role = discord.utils.get(guild.roles, id=await bot_settings.mod_role())
        admin_role = discord.utils.get(guild.roles, id=await bot_settings.admin_role())
        def_overwrite = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            guild.me: discord.PermissionOverwrite(manage_channels=True),
        }
        if mod_role is not None:
            def_overwrite[mod_role] = discord.PermissionOverwrite(
                connect=True,
                manage_channels=True if mod_role.permissions.manage_channels else None)
        if admin_role is not None:
            def_overwrite[admin_role] = discord.PermissionOverwrite(manage_channels=True)
        header = await guild.create_voice_channel(_HEADER_CHANNEL,
                                                  overwrites=def_overwrite,
                                                  reason="Header for PUG voice channels")

        allow_starter = {
            pug.ctx.author: discord.PermissionOverwrite(connect=True)
        }
        allow_starter.update(def_overwrite)
        lobby = await guild.create_voice_channel(_LOBBY_NAME.format(pug_n),
                                                 overwrites=allow_starter,
                                                 reason="Lobby for PUG")

        blue = await guild.create_voice_channel(_TEAM_CHANNEL_NAME.format(pug_n, _BLUE),
                                                overwrites=def_overwrite,
                                                reason="Team channel for PUG")

        orange = await guild.create_voice_channel(_TEAM_CHANNEL_NAME.format(pug_n, _ORANGE),
                                                  overwrites=def_overwrite,
                                                  reason="Team channel for PUG")

        self.channels[pug] = {
            "header": header,
            "lobby": lobby,
            "blue": blue,
            "orange": orange
        }

    @pug_has_voice_channels
    async def on_pug_end(self, pug: Pug):
        """Fires when a PUG ends and deletes its voice channels."""
        for channel in self.channels[pug].values():
            await channel.delete(reason="Deleting temporary PUG channel")
        self.channels.pop(pug)

    @pug_has_voice_channels
    async def on_pug_member_join(self, member: discord.Member, pug: Pug):
        """Fires when a member joins a PUG and allows them access to the lobby."""
        lobby = self.channels[pug].get("lobby")
        await lobby.set_permissions(member, connect=True)

    @pug_has_voice_channels
    async def on_pug_member_remove(self, member: discord.Member, pug: Pug):
        """Fires when a member joins a PUG and denies them access to the lobby
        (and team channels).
        """
        channels = self.channels[pug]
        lobby = channels.get("lobby")
        await lobby.set_permissions(member, overwrite=None)
        blue = channels.get("blue")
        orange = channels.get("orange")
        await blue.set_permissions(member, overwrite=None)
        await orange.set_permissions(member, overwrite=None)

    @match_has_voice_channels
    async def on_pug_match_start(self, match: PugMatch, pug: Pug = None):
        """Fires when a match starts and allows the players access to their
        voice channels, before moving them in.
        """
        channels = self.channels[pug]
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, connect=True)
                await player.move_to(channel)

    @match_has_voice_channels
    async def on_pug_match_end(self, match: PugMatch, pug: Pug = None):
        """Fires when a match ends and denies the players access to their
        voice channels, after moving them to the lobby.
        """
        channels = self.channels[pug]
        lobby = channels.get("lobby")
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, overwrite=None)
                await player.move_to(lobby)
