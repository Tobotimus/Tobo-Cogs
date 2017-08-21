"""Module for R6Pugs cog."""
import discord
from discord.ext import commands
from core import Config
from .log import LOG
from .pug import Pug
from .errors import Forbidden

UNIQUE_ID = 0x315e5521

_DELETE_CHANNEL_AFTER = 10 # seconds

class R6Pugs:
    """Cog to run PuGs for Rainbow Six."""

    def __init__(self):
        self.pugs = []
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(pug_running=False)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def pug(self, ctx: commands.Context):
        """Manage PuGs."""
        if ctx.invoked_subcommand is None:
            await ctx.bot.send_cmd_help(ctx)

    @pug.command(name="start")
    async def pug_start(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Start a new PuG.

        If no channel is specified, a temporary channel will be created."""
        temp_channel = False
        if channel is not None:
            pug = self.get_pug(channel)
            if pug is not None:
                await ctx.send("There is already an ongoing PuG in that channel.")
                return
        else:
            channel = await self.create_temp_channel(ctx.guild)
            temp_channel = True
        original_channel = ctx.channel
        ctx.channel = channel
        LOG.debug("Channel is %r", channel)
        pug = Pug(ctx, temp_channel=temp_channel)
        self.pugs.append(pug)
        pug.add_member(ctx.author)
        await original_channel.send("Pug started in {0.mention}.".format(channel))

    @pug.command(name="stop")
    async def pug_stop(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Stop an ongoing PuG.

        If no channel is specified, it will try to end the PuG in this channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no PuG running in {0.mention}.".format(channel))
            return
        pug.end()

    @pug.command(name="join")
    async def pug_join(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Join a PuG.

        If no channel is specified, it tries to join the PuG in the current channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no Pug running in {0.mention}.".format(channel))
            return
        try:
            pug.add_member(ctx.author)
        except Forbidden:
            await ctx.send("You are not permitted to join that PuG.")
        else:
            await ctx.send("You have successfully joined the PuG in {0.mention}.".format(channel))

    @pug.command(name="leave")
    async def pug_leave(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Leave a PuG.

        If no channel is specified, it tries to leave the PuG in the current channel."""
        if channel is None:
            channel = ctx.channel
        pug = self.get_pug(channel)
        if pug is None:
            await ctx.send("There is no Pug running in {0.mention}.".format(channel))
            return
        try:
            pug.remove_member(ctx.author)
        except ValueError:
            await ctx.send("You are not in that PuG.")
        else:
            await ctx.send("You have successfully left the PuG in {0.mention}.".format(channel))

    def get_pug(self, channel: discord.TextChannel):
        """Get the PuG at the given channel.

        Returns `None` if no such PuG exists."""
        return next((p for p in self.pugs if p.ctx.channel == channel), None)

    async def create_temp_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Create a temporary text channel to run a PuG."""
        # Get the channel name
        name = None
        for idx in range(1, 100):
            name = "pug-{}".format(idx)
            if not any(c.name == name for c in guild.channels):
                break
        return await guild.create_text_channel(name, reason="Temporary PuG channel")

    async def delete_temp_channel(self, channel: discord.TextChannel):
        """Delete a temporary PuG channel."""
        try:
            await channel.delete(reason="Temporary PuG channel")
        except (discord.errors.HTTPException, discord.errors.NotFound):
            pass

    # Events

    async def pug_started(self, pug: Pug):
        """Fires when a PuG is started."""
        ctx = pug.ctx
        LOG.debug("PuG started; #%s in %s", ctx.channel, ctx.guild)
        if pug not in self.pugs:
            self.pugs.append(pug)
        await ctx.send("A PuG has been started here by {0.author.mention}, use"
                       " `{0.prefix}pug join #{0.channel.name}` to join it."
                       "".format(ctx))
        await pug.run_initial_setup()

    async def pug_ended(self, pug: Pug):
        """Fires when a PuG is ended, and removes it from this cog's PuGs."""
        ctx = pug.ctx
        LOG.debug("PuG ended; #%s in %s", ctx.channel, ctx.guild)
        if pug in self.pugs:
            self.pugs.remove(pug)
        msg = "The PuG here has been ended."
        if pug.temp_channel:
            msg += ("\nSince this channel was a temporary channel created specifically for"
                    " this PuG, it will be deleted in 5 minutes.")
            coro = self.delete_temp_channel(ctx.channel)
            LOG.debug("Scheduling deletion of channel #%s", ctx.channel)
            ctx.bot.loop.call_later(_DELETE_CHANNEL_AFTER, ctx.bot.loop.create_task, coro)
        await ctx.send(msg)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Fires when a text channel is deleted and ends any PuGs which it may
         have been running in it.
        """
        if not isinstance(channel, discord.TextChannel):
            return
        pug = self.get_pug(channel)
        if pug is not None and pug in self.pugs:
            self.pugs.remove(pug)
