"""Module for PugVoice cog."""
import discord
from r6pugs.pug import Pug
from r6pugs.match import PugMatch

_HEADER_CHANNEL = "----------------------"
_LOBBY_NAME = "\N{Dog Face} Pug {0} - Lobby"
_TEAM_CHANNEL_NAME = "\N{Dog} Pug {0} {1}"
_BLUE = "\N{Large Blue Diamond}"
_ORANGE = "\N{Large Orange Diamond}"

# decorator
def pug_has_voice_channels(func):
    """Decorator which makes sure the function only runs if
    there are voice channel for it.
    """
    def _decorated(cog, pug: Pug, *args, **kwargs):
        if pug not in cog.channels:
            return
        func(cog, pug, *args, **kwargs)
    return _decorated

class PugVoice:
    """Cog to manage voice channels for PUGs."""

    def __init__(self):
        self.channels = {}

    async def on_pug_start(self, pug: Pug):
        """Fires when a PUG starts and creates new voice channels for it."""
        pug_n = int(pug.channel.name.strip(r'[a-zA-Z]\-'))
        guild = pug.ctx.guild
        deny_connect = {
            guild.default_role: discord.PermissionOverwrite(connect=False)
        }
        header = await guild.create_voice_channel(_HEADER_CHANNEL,
                                                  overwrites=deny_connect,
                                                  reason="Header for PUG voice channels")

        lobby = await guild.create_voice_channel(_LOBBY_NAME.format(pug_n),
                                                 overwrites=deny_connect,
                                                 reason="Lobby for PUG")

        blue = await guild.create_voice_channel(_TEAM_CHANNEL_NAME.format(pug_n, _BLUE),
                                                overwrites=deny_connect,
                                                reason="Team channel for PUG")

        orange = await guild.create_voice_channel(_TEAM_CHANNEL_NAME.format(pug_n, _ORANGE),
                                                  overwrites=deny_connect,
                                                  reason="Team channel for PUG")

        self.channels[pug] = {var.__name__: var for var in (header, lobby, blue, orange)}

    @pug_has_voice_channels
    async def on_pug_end(self, pug: Pug):
        """Fires when a PUG ends and deletes its voice channels."""
        for channel in self.channels[pug].values():
            await channel.delete(reason="Deleting temporary PUG channel")

    @pug_has_voice_channels
    async def on_pug_member_join(self, pug: Pug, member: discord.Member):
        """Fires when a member joins a PUG and allows them access to the lobby."""
        lobby = self.channels[pug].get("lobby")
        await lobby.set_permissions(member, connect=True)

    @pug_has_voice_channels
    async def on_pug_member_leave(self, pug: Pug, member: discord.Member):
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

    @pug_has_voice_channels
    async def on_pug_match_start(self, match: PugMatch):
        """Fires when a match starts and allows the players access to their
        voice channels, before moving them in.
        """
        pug = match.ctx.cog.get_pug(match.channel)
        channels = self.channels[pug]
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, connect=True)
                await player.move_to(channel)

    @pug_has_voice_channels
    async def on_pug_match_end(self, match: PugMatch):
        """Fires when a match ends and denies the players access to their
        voice channels, after moving them to the lobby.
        """
        pug = match.ctx.cog.get_pug(match.channel)
        channels = self.channels[pug]
        lobby = channels.get("lobby")
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, overwrite=None)
                await player.move_to(lobby)
