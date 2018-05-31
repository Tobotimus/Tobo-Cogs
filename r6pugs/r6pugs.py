"""Module for R6Pugs cog."""

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

import pkgutil
import discord
from discord.ext import commands
from redbot.core import Config, checks
from redbot.core.utils.chat_formatting import box
from .log import LOG
from .pug import Pug
from .match import PugMatch
from .errors import Forbidden, ExtensionNotFound
from . import extensions

__all__ = [
    "UNIQUE_ID",
    "pug_starter_or_permissions",
    "R6Pugs",
    "load_extensions",
    "unload_extensions",
    "get_spec",
]

UNIQUE_ID = 0x315e5521

_DELETE_CHANNEL_AFTER = 300  # seconds


# Decorator
def pug_starter_or_permissions(**perms):
    """Check if a user is authorized to manage a PUG."""

    def _check(ctx: commands.Context):
        cog = ctx.bot.get_cog("R6Pugs")
        pug = cog.get_pug(ctx.channel)
        if pug is None:
            return True
        if ctx.author == pug.owner:
            return True
        return checks.check_permissions(ctx, perms)

    return commands.check(_check)


class R6Pugs:
    """Cog to run PUGs for Rainbow Six."""

    def __init__(self, bot):
        self.pugs = []
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_global(loaded_extensions=[])
        self.bot = bot
        bot.loop.create_task(load_extensions(bot, self.conf))

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def pug(self, ctx: commands.Context):
        """Manage PUGs."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @pug.command(name="start")
    async def _pug_start(self, ctx: commands.Context):
        """Start a new PUG.

        A temporary channel category will be created to house the PUG.
        """
        category, channel = await self.create_temp_category(ctx.guild)
        pug = Pug(ctx.bot, category, channel, ctx.author, temp_channels=True)
        self.pugs.append(pug)
        pug.add_member(ctx.author)
        await ctx.send("Pug started in {0.mention}.".format(channel))

    @pug.command(name="stop")
    @pug_starter_or_permissions(manage_messages=True)
    async def _pug_stop(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Stop an ongoing PUG.

        If no channel is specified, it will try to end the PUG in this channel.
        """
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        pug.end()

    @pug.command(name="kick")
    @checks.mod_or_permissions(kick_members=True)
    async def _pug_kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        channel: discord.TextChannel = None,
    ):
        """Kick a member from an ongoing PUG.

        If no channel is specified, it will try to use the PUG in this channel.
        """
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        success = pug.remove_member(member)
        if success is not False:
            await ctx.send(
                "*{0.display_name}* has been kicked from the PUG"
                " in {1.mention}.".format(member, channel)
            )
            return
        await ctx.send("*{0.display_name}* is not in that PUG.")

    @pug.command(name="join")
    async def _pug_join(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Join a PUG.

        If no channel is specified, it tries to join the PUG in the current
        channel.
        """
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        try:
            success = pug.add_member(ctx.author)
        except Forbidden:
            await ctx.send("You are not permitted to join that PUG.")
        else:
            if success is False:
                await ctx.send("You are already in that Pug.")
                return
            await ctx.send("Done.")

    @pug.command(name="leave")
    async def _pug_leave(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Leave a PUG.

        If no channel is specified, it tries to leave the PUG in the current
        channel.
        """
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        success = pug.remove_member(ctx.author)
        if success is False:
            await ctx.send("You are not in that Pug.")
            return
        await ctx.send("Done.")

    @pug.command(name="submit")
    async def _pug_submit(
        self, ctx: commands.Context, your_score: int, their_score: int
    ):
        """Submit scores for a PUG match."""
        pug = self.get_pug(ctx.channel)
        if pug is None:
            await ctx.send("There is no PUG running in this channel.")
            return
        if any(score < 0 for score in (your_score, their_score)):
            await ctx.send("Scores must be positive.")
            return
        match = pug.match
        if match is None:
            await ctx.send("There's no ongoing match for this PUG.")
            return
        if not match.has_member(ctx.author):
            await ctx.send("You are not in the match for this PUG.")
            return
        match.submit_score((your_score, their_score), ctx.author)
        await ctx.send("Score has been submitted.")

    @commands.group()
    async def pugext(self, ctx: commands.Context):
        """Manage extensions to R6Pugs."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            await self._list_extensions(ctx)
            return

    @pugext.command(name="load")
    @checks.is_owner()
    async def _pugext_load(self, ctx: commands.Context, extension: str):
        """Load an extension for R6Pugs."""
        try:
            spec = get_spec(extension)
        except ExtensionNotFound:
            await ctx.send("That extension does not exist.")
        else:
            try:
                ctx.bot.load_extension(spec)
            except Exception as err:
                LOG.exception("Package loading failed", exc_info=err)
                await ctx.send(
                    "Failed to load extension. Check your console or"
                    " logs for details."
                )
            else:
                loaded = await self.conf.loaded_extensions()
                if extension not in loaded:
                    loaded.append(extension)
                    await self.conf.loaded_extensions.set(loaded)
                await ctx.send("Done.")

    @pugext.command(name="unload")
    async def _pugext_unload(self, ctx: commands.Context, extension: str):
        """Unload an extension for R6Pugs."""
        loaded = await self.conf.loaded_extensions()
        if extension in loaded:
            ctx.bot.unload_extension(extension)
            loaded.remove(extension)
            await self.conf.loaded_extensions.set(loaded)
            await ctx.send("Done.")
        else:
            await ctx.send("That extension is not loaded.")

    @pugext.command(name="reload")
    async def _pugext_reload(self, ctx: commands.Context, extension: str):
        """Reload an extension."""
        ctx.bot.unload_extension(extension)
        core_cog = ctx.bot.get_cog("Core")
        if core_cog is None:
            return
        core_cog.cleanup_and_refresh_modules(extension)
        await ctx.invoke(self._pugext_load, extension)

    async def _list_extensions(self, ctx: commands.Context):
        """List extensions to R6Pugs."""
        packages = pkgutil.iter_modules(extensions.__path__)
        loaded = await self.conf.loaded_extensions()
        names = []
        for _, modname, ispkg in packages:
            if ispkg and modname not in loaded:
                names.append(modname)
        if names or loaded:
            if loaded:
                await ctx.send(
                    box("Loaded extensions:\n{}" "".format(", ".join(loaded)))
                )
            if names:
                await ctx.send(
                    box("Available extensions:\n{}" "".format(", ".join(names)))
                )
        else:
            await ctx.send("There are no extensions available.")

    def get_pug(self, channel):
        """Get the PUG running in the given channel or category.

        Returns `None` if no such PUG exists.

        Parameters
        ----------
        channel: Union[discord.TextChannel, discord.CategoryChannel]
            The channel or category which the PUG is running in.

        """
        if isinstance(channel, discord.TextChannel):
            return next((p for p in self.pugs if p.channel == channel), None)
        if isinstance(channel, discord.CategoryChannel):
            return next((p for p in self.pugs if p.category == channel), None)
        raise TypeError("Can only get PUG by its text channel or its" " category.")

    async def create_temp_category(self, guild: discord.Guild):
        """Create a temporary channel category to run a PUG.

        The category will be named with an index, e.g. if the index is 1,
        the category's name will be ``PUG 1``. The index is found by searching
        through the existing categories in the guild and seeing if there are
        any conflicting names.

        Parameters
        ----------
        guild: discord.Guild
            The guild which the category will belong to.

        """
        # Get the channel name
        cat_name = None
        idx = None
        for idx in range(1, 100):
            cat_name = "PUG {}".format(idx)
            if not any(c.name == cat_name for c in guild.categories):
                break
        chan_name = "pug-{}".format(idx)
        category = await guild.create_category(
            cat_name, reason="Temporary PUG category"
        )
        channel = await guild.create_text_channel(
            chan_name, category=category, reason="Temporary PUG channel"
        )
        return (category, channel)

    async def delete_temp_category(self, category: discord.CategoryChannel):
        """Delete a temporary PUG category.

        This will also delete all channels which are contained in this
        category.

        Parameters
        ----------
        category: discord.CategoryChannel
            The temporary category to be deleted.

        """
        try:
            for channel in category.channels:
                await channel.delete(reason="Temporary PUG channel")
            await category.delete(reason="Temporary PUG category")
        except (discord.errors.HTTPException, discord.errors.NotFound):
            pass

    # Events

    async def on_pug_start(self, pug: Pug):
        """Event for a PUG starting."""
        channel = pug.channel
        LOG.debug("PUG started; #%s in %s", channel, channel.guild)
        if pug not in self.pugs:
            self.pugs.append(pug)
        await channel.send(
            "A PUG has been started here by {0.mention},"
            "type `!pug join` in this channel to join it."
            "".format(pug.owner)
        )
        await pug.run_initial_setup()

    async def on_pug_end(self, pug: Pug):
        """Event for a PUG ending."""
        channel = pug.channel
        LOG.debug("PUG ended; #%s in %s", channel, channel.guild)
        if pug in self.pugs:
            self.pugs.remove(pug)
        if channel not in channel.guild.text_channels:
            return  # In case channel was forcibly deleted
        msg = "The PUG here has been ended."
        if pug.settings["temp_channels"]:
            msg += (
                "\nSince this channel was a temporary channel created"
                " specifically for this PUG, it will be deleted in 5 minutes."
            )
            coro = self.delete_temp_category(pug.category)
            LOG.debug("Scheduling deletion of category %s", pug.category)
            pug.bot.loop.call_later(
                _DELETE_CHANNEL_AFTER, pug.bot.loop.create_task, coro
            )
        await channel.send(msg)

    async def on_pug_member_join(self, member: discord.Member, pug: Pug):
        """Event for a member being added to a PUG."""
        n_members = len(pug.queue)
        msg = ""
        if n_members < 10:

            msg = (
                "{0.mention} has joined the Pug, {1} more player{2}"
                " needed to start the match!"
                "".format(member, 10 - n_members, "s are" if n_members != 9 else " is")
            )
        elif n_members == 10:
            msg = (
                "{0.mention} is the 10th player in the Pug, a match"
                " will start now!".format(member)
            )
        else:
            msg = (
                "{0.mention} has joined the Pug and is at position"
                " {1} in the queue.".format(member, n_members - 10)
            )
        await pug.channel.send(msg)

    async def on_pug_member_remove(self, member: discord.Member, pug: Pug):
        """Event for a member being removed from a PUG."""
        n_members = len(pug.queue)
        msg = ""
        if n_members < 10:
            msg = (
                "{0.mention} has left the Pug, {1} more player{2}"
                " now needed to start the match."
                "".format(member, 10 - n_members, "s are" if n_members != 9 else " is")
            )
        else:
            msg = "{0.mention} has left the Pug.".format(member)
        await pug.channel.send(msg)

    async def on_tenth_player(self, pug: Pug):
        """Event for when 10 players have joined a PUG."""
        LOG.debug("Event running for 10th player")
        pug.match_running = True
        kicked_players = await pug.ready_up()
        if kicked_players:
            while len(pug.queue) >= 10:
                kicked_players = await pug.refill(len(kicked_players))
                if not kicked_players:
                    break
            else:
                pug.match_running = False
                needed = 10 - len(pug.queue)
                plural = " is" if needed == 1 else "s are"
                await pug.channel.send(
                    "{} more player{} needed to start the match!"
                    "".format(needed, plural)
                )
                return
        await pug.run_match()

    async def on_pug_match_start(self, match: PugMatch):
        """Event for a PUG match starting."""
        channel = match.channel
        LOG.debug("Match starting; #%s in %s", channel, channel.guild)
        await channel.send("The match is starting!")
        await match.send_summary()

    async def on_pug_match_end(self, match: PugMatch):
        """Event for a PUG match ending."""
        channel = match.channel
        LOG.debug("Match ending; #%s in %s", channel, channel.guild)
        await channel.send("The match has ended.")
        await match.send_summary()
        pug = self.get_pug(channel)
        if len(pug.queue) >= 10:
            await channel.send(
                "There will now be a 1 minute break before the next match" " starts."
            )

            def _allow_match(pug: Pug):
                pug.match_running = False

            match.bot.loop.call_later(58, _allow_match, pug)
            match.bot.loop.call_later(60, pug.check_tenth_player)
        losing_score = min(score for score in match.final_score)
        losing_team_idx = match.final_score.index(losing_score)
        losing_team = match.teams[losing_team_idx]
        if pug.settings["losers_leave"] and match.final_score is not None:
            await channel.send(
                "Losers are being removed from the PUG, they may use"
                " `!pug join` to rejoin the queue."
            )
            for player in losing_team:
                pug.remove_member(player)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Event for a guild channel being deleted.

        If the guild channel is a PUG channel or category, it  will end the
        PUG running there.
        """
        if not isinstance(channel, (discord.TextChannel, discord.CategoryChannel)):
            return
        pug = self.get_pug(channel)
        if pug is not None and pug in self.pugs:
            pug.end()

    def __unload(self):
        self.bot.loop.create_task(unload_extensions(self.bot, self.conf))


async def load_extensions(bot, conf: Config):
    """Load extensions in the `conf.loaded_extensions` list."""
    loaded = await conf.loaded_extensions()
    for extension in loaded:
        spec = get_spec(extension)
        if spec is None:
            loaded.remove(extension)
            continue
        try:
            bot.load_extension(spec)
        except Exception as err:
            LOG.exception("Package loading failed", exc_info=err)
            loaded.remove(extension)
    await conf.loaded_extensions.set(loaded)


async def unload_extensions(bot, conf: Config):
    """Unload extensions in the `conf.loaded_extensions` list."""
    loaded = await conf.loaded_extensions()
    for extension in loaded:
        bot.unload_extension(extension)


def get_spec(extension: str):
    """Get the spec for a package in the `.extensions` folder."""
    packages = pkgutil.iter_modules(extensions.__path__)
    spec = None
    for finder, module_name, _ in packages:
        if extension == module_name:
            spec = finder.find_spec(extension)
            break
    else:
        raise ExtensionNotFound(extension)
    return spec
