"""Module for PugVoice cog."""

# Copyright (c) 2017-2018 Tobotimus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
import discord
from r6pugs import Pug, PugMatch

__all__ = ["pug_has_voice_channels", "match_has_voice_channels", "PugVoice"]

_LOBBY_NAME = "\N{Dog Face} Lobby"
_BLUE = "\N{Large Blue Diamond} Blue Team"
_ORANGE = "\N{Large Orange Diamond} Orange Team"


# decorators
def pug_has_voice_channels(func):
    """Check if a pug has voice channels before running the coroutine."""

    async def _decorated(cog, *args, **kwargs):
        pug = next((arg for arg in args if isinstance(arg, Pug)), None)
        if pug is None or pug not in cog.channels:
            return
        await func(cog, *args, **kwargs)

    return _decorated


def match_has_voice_channels(func):
    """Check if a match has voice channels before running the coroutine."""

    async def _decorated(cog, *args, **kwargs):
        match = next((arg for arg in args if isinstance(arg, PugMatch)), None)
        if match is None:
            return
        args = list(args)
        args.remove(match)
        main_cog = match.bot.get_cog("R6Pugs")
        pug = main_cog.get_pug(match.channel)
        if pug is None or pug not in cog.channels:
            return
        await func(cog, match, pug, *args, **kwargs)

    return _decorated


class PugVoice:
    """Cog to manage voice channels for PUGs."""

    def __init__(self):
        self.channels = {}

    async def on_pug_start(self, pug: Pug):
        """Event for a PUG starting.

        Creates the voice channels for the PUG under its channel category.
        """
        category = pug.category
        pug_n = re.findall(r"\d+", category.name)
        if not pug_n:
            return
        pug_n = int(pug_n.pop())
        guild = category.guild
        bot_settings = pug.bot.db.guild(guild)
        mod_role = await bot_settings.mod_role()
        mod_role = next((r for r in guild.roles if r.id == mod_role), None)
        admin_role = await bot_settings.admin_role()
        admin_role = next((r for r in guild.roles if r.id == admin_role), None)
        def_overwrite = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            guild.me: discord.PermissionOverwrite(manage_channels=True),
        }
        if mod_role is not None:
            def_overwrite[mod_role] = discord.PermissionOverwrite(
                connect=True,
                manage_channels=True if mod_role.permissions.manage_channels else None,
            )
        if admin_role is not None:
            def_overwrite[admin_role] = discord.PermissionOverwrite(
                manage_channels=True
            )

        allow_starter = {pug.owner: discord.PermissionOverwrite(connect=True)}
        allow_starter.update(def_overwrite)
        lobby = await guild.create_voice_channel(
            _LOBBY_NAME,
            category=category,
            overwrites=allow_starter,
            reason="Lobby for PUG",
        )

        blue = await guild.create_voice_channel(
            _BLUE,
            category=category,
            overwrites=def_overwrite,
            reason="Team channel for PUG",
        )

        orange = await guild.create_voice_channel(
            _ORANGE,
            category=category,
            overwrites=def_overwrite,
            reason="Team channel for PUG",
        )

        self.channels[pug] = {"lobby": lobby, "blue": blue, "orange": orange}

    @pug_has_voice_channels
    async def on_pug_end(self, pug: Pug):
        """Event for a PUG ending."""
        self.channels.pop(pug)

    @pug_has_voice_channels
    async def on_pug_member_join(self, member: discord.Member, pug: Pug):
        """Event for a member being added to a PUG.

        Allows for the member to connect to and speak in the PUG lobby.
        """
        lobby = self.channels[pug].get("lobby")
        await lobby.set_permissions(member, connect=True)

    @pug_has_voice_channels
    async def on_pug_member_remove(self, member: discord.Member, pug: Pug):
        """Event for a member being removed from a PUG.

        Removes any permissions which were previously granted to them by this
        extension.
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
        """Event for a PUG match starting.

        Players will be given permissions to connect to and speak in their
        team's voice channels. Any players who are connected to a channel will
        be moved to their respective team channel.
        """
        channels = self.channels[pug]
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, connect=True)
                try:
                    await player.move_to(channel)
                except discord.Forbidden:
                    pass

    @match_has_voice_channels
    async def on_pug_match_end(self, match: PugMatch, pug: Pug = None):
        """Event for a PUG match ending.

        Players are moved back to the PUG lobby, and their permissions for
        the team channels are revoked.
        """
        channels = self.channels[pug]
        lobby = channels.get("lobby")
        channels = (channels.get("blue"), channels.get("orange"))
        for team, channel in zip(match.teams, channels):
            for player in team:
                await channel.set_permissions(player, overwrite=None)
                try:
                    await player.move_to(lobby)
                except discord.Forbidden:
                    pass
