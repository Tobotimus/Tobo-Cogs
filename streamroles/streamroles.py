"""Module for the StreamRoles cog."""

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

import asyncio
import contextlib
import logging
from typing import List, Optional, Tuple, Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as chatutils, menus, predicates

log = logging.getLogger("red.streamroles")

UNIQUE_ID = 0x923476AF


class StreamRoles(commands.Cog):
    """Give current twitch streamers in your server a role."""

    # Set using [p]eval or something rather and the streamrole will be assigned simply
    # whenever someone is streaming, regardless of whether or not they have a linked
    # Twitch account. Makes for easier black-box testing.
    DEBUG_MODE = False

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.conf = Config.get_conf(self, force_registration=True, identifier=UNIQUE_ID)
        self.conf.register_guild(
            streamer_role=None,
            game_whitelist=[],
            mode="blacklist",
            alerts__enabled=False,
            alerts__channel=None,
        )
        self.conf.register_member(
            blacklisted=False, whitelisted=False, alert_messages={}
        )
        self.conf.register_role(blacklisted=False, whitelisted=False)

    async def initialize(self) -> None:
        """Initialize the cog."""
        for guild in self.bot.guilds:
            await self._update_guild(guild)

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.group(autohelp=True, aliases=["streamroles"])
    async def streamrole(self, ctx: commands.Context):
        """Manage settings for StreamRoles."""
        pass

    @streamrole.command()
    async def setmode(self, ctx: commands.Context, *, mode: str):
        """Set the user filter mode to blacklist or whitelist."""
        mode = mode.lower()
        if mode not in ("blacklist", "whitelist"):
            await ctx.send("Mode must be `blacklist` or `whitelist`.")
            return
        await self.conf.guild(ctx.guild).mode.set(mode)
        await self._update_guild(ctx.guild)
        await ctx.tick()

    @streamrole.group(autohelp=True)
    async def whitelist(self, ctx: commands.Context):
        """Manage the whitelist."""
        pass

    @whitelist.command(name="add")
    async def white_add(
        self,
        ctx: commands.Context,
        *,
        user_or_role: Union[discord.Member, discord.Role],
    ):
        """Add a member or role to the whitelist."""
        if isinstance(user_or_role, discord.Member):
            await self.conf.member(user_or_role).whitelisted.set(True)
            await self._update_member(user_or_role)
        else:
            await self.conf.role(user_or_role).whitelisted.set(True)
            await self._update_members_with_role(user_or_role)
        await ctx.tick()

    @whitelist.command(name="remove")
    async def white_remove(
        self,
        ctx: commands.Context,
        *,
        user_or_role: Union[discord.Member, discord.Role],
    ):
        """Remove a member or role from the whitelist."""
        if isinstance(user_or_role, discord.Member):
            await self.conf.member(user_or_role).whitelisted.set(False)
            await self._update_member(user_or_role)
        else:
            await self.conf.role(user_or_role).whitelisted.set(False)
            await self._update_members_with_role(user_or_role)
        await ctx.tick()

    @checks.bot_has_permissions(embed_links=True)
    @whitelist.command(name="show")
    async def white_show(self, ctx: commands.Context):
        """Show the whitelisted members and roles in this server."""
        members, roles = await self._get_filter_list(ctx.guild, "whitelist")
        if not (members or roles):
            await ctx.send("The whitelist is empty.")
            return
        embed = discord.Embed(
            title="StreamRoles Whitelist", colour=await ctx.embed_colour()
        )
        if members:
            embed.add_field(name="Members", value="\n".join(map(str, members)))
        if roles:
            embed.add_field(name="Roles", value="\n".join(map(str, roles)))
        await ctx.send(embed=embed)

    @streamrole.group(autohelp=True)
    async def blacklist(self, ctx: commands.Context):
        """Manage the blacklist."""
        pass

    @blacklist.command(name="add")
    async def black_add(
        self,
        ctx: commands.Context,
        *,
        user_or_role: Union[discord.Member, discord.Role],
    ):
        """Add a member or role to the blacklist."""
        if isinstance(user_or_role, discord.Member):
            await self.conf.member(user_or_role).blacklisted.set(True)
            await self._update_member(user_or_role)
        else:
            await self.conf.role(user_or_role).blacklisted.set(True)
            await self._update_members_with_role(user_or_role)
        await ctx.tick()

    @blacklist.command(name="remove")
    async def black_remove(
        self,
        ctx: commands.Context,
        *,
        user_or_role: Union[discord.Member, discord.Role],
    ):
        """Remove a member or role from the blacklist."""
        if isinstance(user_or_role, discord.Member):
            await self.conf.member(user_or_role).blacklisted.set(False)
            await self._update_member(user_or_role)
        else:
            await self.conf.role(user_or_role).blacklisted.set(False)
            await self._update_members_with_role(user_or_role)
        await ctx.tick()

    @checks.bot_has_permissions(embed_links=True)
    @blacklist.command(name="show")
    async def black_show(self, ctx: commands.Context):
        """Show the blacklisted members and roles in this server."""
        members, roles = await self._get_filter_list(ctx.guild, "blacklist")
        if not (members or roles):
            await ctx.send("The blacklist is empty.")
            return
        embed = discord.Embed(
            title="StreamRoles Blacklist", colour=await ctx.embed_colour()
        )
        if members:
            embed.add_field(name="Members", value="\n".join(map(str, members)))
        if roles:
            embed.add_field(name="Roles", value="\n".join(map(str, roles)))
        await ctx.send(embed=embed)

    @streamrole.group(autohelp=True)
    async def games(self, ctx: commands.Context):
        """Manage the game whitelist.

        Adding games to the whitelist will make the bot only add the streamrole
        to members streaming those games. If the game whitelist is empty, the
        game being streamed won't be checked before adding the streamrole.
        """
        pass

    @games.command(name="add")
    async def games_add(self, ctx: commands.Context, *, game: str):
        """Add a game to the game whitelist.

        This should *exactly* match the name of the game being played
        by the streamer as shown in Discord or on Twitch.
        """
        async with self.conf.guild(ctx.guild).game_whitelist() as whitelist:
            whitelist.append(game)
        await self._update_guild(ctx.guild)
        await ctx.tick()

    @games.command(name="remove")
    async def games_remove(self, ctx: commands.Context, *, game: str):
        """Remove a game from the game whitelist."""
        async with self.conf.guild(ctx.guild).game_whitelist() as whitelist:
            try:
                whitelist.remove(game)
            except ValueError:
                await ctx.send("That game is not in the whitelist.")
                return
        await self._update_guild(ctx.guild)
        await ctx.tick()

    @checks.bot_has_permissions(embed_links=True)
    @games.command(name="show")
    async def games_show(self, ctx: commands.Context):
        """Show the game whitelist for this server."""
        whitelist = await self.conf.guild(ctx.guild).game_whitelist()
        if not whitelist:
            await ctx.send("The game whitelist is empty.")
            return
        embed = discord.Embed(
            title="StreamRoles Game Whitelist",
            description="\n".join(whitelist),
            colour=await ctx.embed_colour(),
        )
        await ctx.send(embed=embed)

    @games.command(name="clear")
    async def games_clear(self, ctx: commands.Context):
        """Clear the game whitelist for this server."""
        msg = await ctx.send(
            "This will clear the game whitelist for this server. "
            "Are you sure you want to do this?"
        )
        menus.start_adding_reactions(msg, predicates.ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = predicates.ReactionPredicate.yes_or_no(msg)
        try:
            message = await ctx.bot.wait_for("reaction_add", check=pred)
        except asyncio.TimeoutError:
            message = None
        if message is not None and pred.result is True:
            await self.conf.guild(ctx.guild).game_whitelist.clear()
            await self._update_guild(ctx.guild)
            await ctx.send("Done. The game whitelist has been cleared.")
        else:
            await ctx.send("The action was cancelled.")

    @streamrole.group()
    async def alerts(self, ctx: commands.Context):
        """Manage streamalerts for those who receive the streamrole."""

    @alerts.command(name="setenabled")
    async def alerts_setenabled(self, ctx: commands.Context, true_or_false: bool):
        """Enable or disable streamrole alerts."""
        await self.conf.guild(ctx.guild).alerts.enabled.set(true_or_false)
        await ctx.tick()

    @alerts.command(name="setchannel")
    async def alerts_setchannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Set the channel for streamrole alerts."""
        await self.conf.guild(ctx.guild).alerts.channel.set(channel.id)
        await ctx.tick()

    async def _get_filter_list(
        self, guild: discord.Guild, mode: str
    ) -> Tuple[List[discord.Member], List[discord.Role]]:
        all_member_data = await self.conf.all_members(guild)
        all_role_data = await self.conf.all_roles()
        mode = mode + "ed"
        member_ids = (u for u, d in all_member_data.items() if d.get(mode))
        role_ids = (u for u, d in all_role_data.items() if d.get(mode))
        members = list(filter(None, map(guild.get_member, member_ids)))
        roles = list(filter(None, map(guild.get_role, role_ids)))
        return members, roles

    @streamrole.command()
    async def setrole(self, ctx: commands.Context, *, role: discord.Role):
        """Set the role which is given to streamers."""
        await self.conf.guild(ctx.guild).streamer_role.set(role.id)
        await ctx.send(
            "Done. Streamers will now be given the {} role when "
            "they go live.".format(role.name)
        )

    async def get_streamer_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get the streamrole for this guild.

        Arguments
        ---------
        guild : discord.Guild
            The guild to retrieve the streamer role for.

        Returns
        -------
        Optional[discord.Role]
            The role given to streaming users in this guild. ``None``
            if not set.
        """
        role_id = await self.conf.guild(guild).streamer_role()
        if not role_id:
            return
        try:
            role = next(r for r in guild.roles if r.id == role_id)
        except StopIteration:
            return
        else:
            return role

    async def get_alerts_channel(
        self, guild: discord.Guild
    ) -> Optional[discord.TextChannel]:
        """Get the alerts channel for this guild.

        Arguments
        ---------
        guild : discord.Guild
            The guild to retrieve the alerts channel for.

        Returns
        -------
        Optional[discord.TextChannel]
            The channel where alerts are posted in this guild. ``None``
            if not set or enabled.
        """
        alerts_data = await self.conf.guild(guild).alerts.all()
        if not alerts_data["enabled"]:
            return
        return guild.get_channel(alerts_data["channel"])

    async def _update_member(
        self,
        member: discord.Member,
        role: Optional[discord.Role] = None,
        alerts_channel: Optional[discord.Role] = ...,
    ) -> None:
        role = role or await self.get_streamer_role(member.guild)
        if role is None:
            return

        channel = (
            alerts_channel
            if alerts_channel is not ...
            else await self.get_alerts_channel(member.guild)
        )

        activity = member.activity
        if activity is not None and isinstance(activity, discord.Streaming):
            if self.DEBUG_MODE is True:
                stream = True
            else:
                stream = activity.twitch_name
        else:
            stream = None

        has_role = role in member.roles
        if stream and await self._is_allowed(member):
            game = member.activity.details
            games = await self.conf.guild(member.guild).game_whitelist()
            if not games or game in games:
                if not has_role:
                    log.debug("Adding streamrole %s to member %s", role.id, member.id)
                    await member.add_roles(role)
                    if channel:
                        await self._post_alert(member, channel)
                return

        if has_role:
            log.debug("Removing streamrole %s from member %s", role.id, member.id)
            await member.remove_roles(role)
            if channel:
                await self._remove_alert(member, channel)

    async def _update_members_with_role(self, role: discord.Role) -> None:
        streamer_role = await self.get_streamer_role(role.guild)
        if streamer_role is None:
            return

        alerts_channel = await self.get_alerts_channel(role.guild)

        if await self.conf.guild(role.guild).mode() == "blacklist":
            for member in role.members:
                if streamer_role in member.roles:
                    log.debug(
                        "Removing streamrole %s from member %s after role %s was "
                        "blacklisted",
                        streamer_role.id,
                        member.id,
                        role.id,
                    )
                    await member.remove_roles(
                        streamer_role,
                        reason=f"Removing streamrole after {role} role was blacklisted",
                    )
        else:
            for member in role.members:
                await self._update_member(member, streamer_role, alerts_channel)

    async def _update_guild(self, guild: discord.Guild) -> None:
        streamer_role = await self.get_streamer_role(guild)
        if streamer_role is None:
            return

        alerts_channel = await self.get_alerts_channel(guild)

        for member in guild.members:
            await self._update_member(member, streamer_role, alerts_channel)

    async def _post_alert(
        self, member: discord.Member, channel: discord.TextChannel
    ) -> discord.Message:
        activity = member.activity
        content = (
            f"{chatutils.bold(member.display_name)} is now live on Twitch, playing "
            f"{chatutils.italics(str(activity.details))}:\n\n"
            f"{chatutils.italics(activity.name)}\n\n{activity.url}"
        )
        msg = await channel.send(content)
        await self.conf.member(member).alert_messages.set_raw(
            str(channel.id), value=msg.id
        )
        return msg

    async def _remove_alert(
        self, member: discord.Member, channel: discord.TextChannel
    ) -> None:
        conf_group = self.conf.member(member).alert_messages
        msg_id = await conf_group.get_raw(str(channel.id), default=None)
        if msg_id is None:
            return
        await conf_group.clear_raw(str(channel.id))

        msg: Optional[discord.Message] = discord.utils.get(
            getattr(self.bot, "cached_messages", ()), id=msg_id
        )
        if msg is None:
            try:
                msg = await channel.fetch_message(msg_id)
            except discord.NotFound:
                return

        with contextlib.suppress(discord.NotFound):
            await msg.delete()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Update any members in a new guild."""
        await self._update_guild(guild)

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Apply or remove streamrole when a user's activity changes."""
        if before.activity != after.activity:
            await self._update_member(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Update a new member who joins."""
        await self._update_member(member)

    async def _is_allowed(self, member: discord.Member) -> bool:
        if await self.conf.guild(member.guild).mode() == "blacklist":
            return not await self._is_blacklisted(member)
        else:
            return await self._is_whitelisted(member)

    async def _is_whitelisted(self, member: discord.Member) -> bool:
        if await self.conf.member(member).whitelisted():
            return True
        for role in member.roles:
            if await self.conf.role(role).whitelisted():
                return True
        return False

    async def _is_blacklisted(self, member: discord.Member) -> bool:
        if await self.conf.member(member).blacklisted():
            return True
        for role in member.roles:
            if await self.conf.role(role).blacklisted():
                return True
        return False
