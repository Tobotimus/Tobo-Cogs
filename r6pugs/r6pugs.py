"""Module for R6Pugs cog."""
import pkgutil
import discord
from discord.ext import commands
from core import Config, checks
from core.bot import Red
from core.utils.chat_formatting import box
from .log import LOG
from .pug import Pug
from .match import PugMatch
from .errors import Forbidden, ExtensionNotFound
from . import extensions

UNIQUE_ID = 0x315e5521

_DELETE_CHANNEL_AFTER = 300 # seconds

# Decorator
def pug_starter_or_permissions(**perms):
    """Check if a user is authorized to manage a PUG."""
    def _check(ctx: commands.Context):
        pug = ctx.cog.get_pug(ctx.channel)
        if pug is None:
            return True
        is_starter = ctx.author == pug.ctx.author
        if is_starter:
            return True
        return checks.check_permissions(ctx, perms)
    return commands.check(_check)

class R6Pugs:
    """Cog to run PUGs for Rainbow Six."""

    def __init__(self, bot: Red):
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
            await ctx.bot.send_cmd_help(ctx)

    @pug.command(name="start")
    async def _pug_start(self, ctx: commands.Context):
        """Start a new PUG.

        A temporary channel will be created to house the PUG."""
        channel = await self.create_temp_channel(ctx.guild)
        original_channel = ctx.channel
        ctx.channel = channel
        pug = Pug(ctx, temp_channel=True)
        self.pugs.append(pug)
        pug.add_member(ctx.author)
        await original_channel.send("Pug started in {0.mention}.".format(channel))

    @pug.command(name="stop")
    @pug_starter_or_permissions(manage_messages=True)
    async def _pug_stop(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Stop an ongoing PUG.

        If no channel is specified, it will try to end the PUG in this channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        pug.end()

    @pug.command(name="kick")
    @checks.mod_or_permissions(kick_members=True)
    async def _pug_kick(self, ctx: commands.Context, member: discord.Member,
                        channel: discord.TextChannel=None):
        """Kick a member from an ongoing PUG.

        If no channel is specified, it will try to use the PUG in this channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        success = pug.remove_member(member)
        if success is not False:
            await ctx.send("*{0.display_name}* has been kicked from the PUG in {1.mention}."
                           "".format(member, channel))
            return
        await ctx.send("*{0.display_name}* is not in that PUG.")

    @pug.command(name="join")
    async def _pug_join(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Join a PUG.

        If no channel is specified, it tries to join the PUG in the current channel."""
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
    async def _pug_leave(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Leave a PUG.

        If no channel is specified, it tries to leave the PUG in the current channel."""
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
    async def _pug_submit(self, ctx: commands.Context, your_score: int, their_score: int):
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
            await ctx.bot.send_cmd_help(ctx)
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
                await ctx.send("Failed to load extension. Check your console or"
                               " logs for details.")
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
        core = ctx.bot.get_cog("Core")
        if core is None:
            return
        core.cleanup_and_refresh_modules(extension)
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
                await ctx.send(box("Loaded extensions:\n{}"
                                   "".format(", ".join(loaded))))
            if names:
                await ctx.send(box("Available extensions:\n{}"
                                   "".format(", ".join(names))))
        else:
            await ctx.send("There are no extensions available.")

    def get_pug(self, channel: discord.TextChannel):
        """Get the PUG at the given channel.

        Returns `None` if no such PUG exists."""
        return next((p for p in self.pugs if p.ctx.channel == channel), None)

    async def create_temp_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Create a temporary text channel to run a PUG."""
        # Get the channel name
        name = None
        for idx in range(1, 100):
            name = "pug-{}".format(idx)
            if not any(c.name == name for c in guild.text_channels):
                break
        return await guild.create_text_channel(name, reason="Temporary PUG channel")

    async def delete_temp_channel(self, channel: discord.TextChannel):
        """Delete a temporary PUG channel."""
        try:
            await channel.delete(reason="Temporary PUG channel")
        except (discord.errors.HTTPException, discord.errors.NotFound):
            pass

    # Events

    async def on_pug_start(self, pug: Pug):
        """Fires when a PUG is started."""
        ctx = pug.ctx
        LOG.debug("PUG started; #%s in %s", ctx.channel, ctx.guild)
        if pug not in self.pugs:
            self.pugs.append(pug)
        await ctx.send("A PUG has been started here by {0.author.mention}, use"
                       " `{0.prefix}pug join #{0.channel.name}` to join it."
                       "".format(ctx))
        await pug.run_initial_setup()

    async def on_pug_end(self, pug: Pug):
        """Fires when a PUG is ended, and removes it from this cog's PUGs."""
        ctx = pug.ctx
        LOG.debug("PUG ended; #%s in %s", ctx.channel, ctx.guild)
        if pug in self.pugs:
            self.pugs.remove(pug)
        if pug.ctx.channel not in pug.ctx.guild.text_channels:
            return # In case channel was forcibly deleted
        msg = "The PUG here has been ended."
        if pug.settings["temp_channel"]:
            msg += ("\nSince this channel was a temporary channel created specifically for"
                    " this PUG, it will be deleted in 5 minutes.")
            coro = self.delete_temp_channel(ctx.channel)
            LOG.debug("Scheduling deletion of channel #%s", ctx.channel)
            ctx.bot.loop.call_later(_DELETE_CHANNEL_AFTER, ctx.bot.loop.create_task, coro)
        await ctx.send(msg)

    async def on_pug_member_join(self, member: discord.Member, pug: Pug):
        """Fires when a member is added to a Pug."""
        n_members = len(pug.queue)
        msg = ""
        if n_members < 10:

            msg = ("{0.mention} has joined the Pug, {1} more player{2}"
                   " needed to start the match!"
                   "".format(member, 10 - n_members,
                             "s are" if n_members != 9 else " is"))
        elif n_members == 10:
            msg = ("{0.mention} is the 10th player in the Pug, a match"
                   " will start now!".format(member))
        else:
            msg = ("{0.mention} has joined the Pug and is at position"
                   " {1} in the queue.".format(member, n_members - 10))
        await pug.ctx.send(msg)

    async def on_pug_member_remove(self, member: discord.Member, pug: Pug):
        """Fires when a member is removed from a Pug."""
        n_members = len(pug.queue)
        msg = ""
        if n_members < 10:
            msg = ("{0.mention} has left the Pug, {1} more player{2}"
                   " now needed to start the match."
                   "".format(member, 10 - n_members,
                             "s are" if n_members != 9 else " is"))
        else:
            msg = "{0.mention} has left the Pug.".format(member)
        await pug.ctx.send(msg)

    async def on_tenth_player(self, pug: Pug):
        """Fires when there are 10 players waiting in a queue
         but no match is starting.
        """
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
                await pug.ctx.send("{} more player{} needed to start the match!"
                                   "".format(needed, plural))
                return
        await pug.run_match()

    async def on_pug_match_start(self, match: PugMatch):
        """Fires when a PUG match starts."""
        ctx = match.ctx
        LOG.debug("Match starting; #%s in %s", ctx.channel, ctx.guild)
        await ctx.send("The match is starting!")
        await match.send_summary()

    async def on_pug_match_end(self, match: PugMatch):
        """Fires when a PUG match ends."""
        ctx = match.ctx
        LOG.debug("Match ending; #%s in %s", ctx.channel, ctx.guild)
        await ctx.send("The match has ended.")
        await match.send_summary()
        pug = self.get_pug(ctx.channel)
        if len(pug.queue) >= 10:
            await ctx.send("There will now be a 1 minute break before the next match starts.")
            def _allow_match(pug: Pug):
                pug.match_running = False
            ctx.bot.loop.call_later(58, _allow_match, pug)
            ctx.bot.loop.call_later(60, pug.check_tenth_player)
        losing_score = min(score for score in match.final_score)
        losing_team_idx = match.final_score.index(losing_score)
        losing_team = match.teams[losing_team_idx]
        if pug.settings["losers_leave"] and match.final_score is not None:
            await ctx.send("Losers are being removed from the PUG, they may use"
                           " `{}pug join #{}` to rejoin the queue."
                           "".format(ctx.prefix, ctx.channel.name))
            for player in losing_team:
                pug.remove_member(player)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Fires when a text channel is deleted and ends any PUGs which it may
         have been running in it.
        """
        if not isinstance(channel, discord.TextChannel):
            return
        pug = self.get_pug(channel)
        if pug is not None and pug in self.pugs:
            pug.end()

    def __unload(self):
        self.bot.loop.create_task(unload_extensions(self.bot, self.conf))

async def load_extensions(bot: Red, conf: Config):
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

async def unload_extensions(bot: Red, conf: Config):
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
