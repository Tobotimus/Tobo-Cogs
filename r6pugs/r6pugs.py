"""Module for R6Pugs cog."""
import discord
from discord.ext import commands
from core import Config
from .log import LOG
from .pug import Pug
from .match import PugMatch
from .errors import Forbidden

UNIQUE_ID = 0x315e5521

_DELETE_CHANNEL_AFTER = 300 # seconds

class R6Pugs:
    """Cog to run PUGs for Rainbow Six."""

    def __init__(self):
        self.pugs = []
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def pug(self, ctx: commands.Context):
        """Manage PUGs."""
        if ctx.invoked_subcommand is None:
            await ctx.bot.send_cmd_help(ctx)

    @pug.command(name="start")
    async def pug_start(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Start a new PUG.

        If no channel is specified, a temporary channel will be created."""
        temp_channel = False
        if channel is not None:
            pug = self.get_pug(channel)
            if pug is not None:
                await ctx.send("There is already an ongoing PUG in that channel.")
                return
        else:
            channel = await self.create_temp_channel(ctx.guild)
            temp_channel = True
        original_channel = ctx.channel
        ctx.channel = channel
        pug = Pug(ctx, temp_channel=temp_channel)
        self.pugs.append(pug)
        pug.add_member(ctx.author)
        await original_channel.send("Pug started in {0.mention}.".format(channel))

    @pug.command(name="stop")
    async def pug_stop(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Stop an ongoing PUG.

        If no channel is specified, it will try to end the PUG in this channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        pug.end()

    @pug.command(name="join")
    async def pug_join(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Join a PUG.

        If no channel is specified, it tries to join the PUG in the current channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        try:
            pug.add_member(ctx.author)
        except Forbidden:
            await ctx.send("You are not permitted to join that PUG.")
        else:
            await ctx.send("You have successfully joined the PUG in {0.mention}.".format(channel))

    @pug.command(name="leave")
    async def pug_leave(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Leave a PUG.

        If no channel is specified, it tries to leave the PUG in the current channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PUG running in {0.mention}.".format(channel))
            return
        try:
            pug.remove_member(ctx.author)
        except ValueError:
            await ctx.send("You are not in that PUG.")
        else:
            await ctx.send("You have successfully left the PUG in {0.mention}.".format(channel))

    @pug.command(name="submit")
    async def pug_submit(self, ctx: commands.Context, your_score: int, their_score: int):
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
    async def pugaddons(self, ctx: commands.Context):
        """Manage addons for this package."""
        if not ctx.invoked_subcommand:
            await ctx.bot.send_cmd_help(ctx)

    @pugaddons.command(name="stats")
    async def addon_stats(self, ctx: commands.Context):
        """Enable / disable the stats addon."""
        from .pugstats import PugStats
        cog = ctx.bot.get_cog(PugStats.__name__)
        if cog is None:
            ctx.bot.add_cog(PugStats())
            await ctx.send("The stats addon has been enabled.")
        else:
            ctx.bot.remove_cog(PugStats.__name__)
            await ctx.send("The stats addon has been disabled.")

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

    async def on_tenth_player(self, pug: Pug):
        """Fires when there are 10 players waiting in a queue
         but no match is starting.
        """
        pug.match_running = True
        while len(pug.queue) > 10:
            success = await pug.ready_up()
            if success:
                await pug.run_match()
                break

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
        losing_score = min(score for score in match.final_score)
        losing_team_idx = match.final_score.index(losing_score)
        losing_team = match.teams[losing_team_idx]
        if pug.settings["losers_leave"] and match.final_score is not None:
            await ctx.send("Losers are being removed from the PUG, they may use"
                           " `{}pug join #{}` to rejoin the queue."
                           "".format(ctx.prefix, ctx.channel.name))
            for player in losing_team:
                pug.remove_member(player)
            if len(pug.queue) > 10:
                ctx.bot.dispatch("tenth_player", pug)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Fires when a text channel is deleted and ends any PUGs which it may
         have been running in it.
        """
        if not isinstance(channel, discord.TextChannel):
            return
        pug = self.get_pug(channel)
        if pug is not None and pug in self.pugs:
            pug.end()
