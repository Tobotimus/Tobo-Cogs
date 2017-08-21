"""Module for R6Pugs cog."""
import discord
from discord.ext import commands
from core import Config, checks
from core.bot import Red
from .log import LOG
from .pug import Pug
from .errors import Forbidden

UNIQUE_ID = 0x315e5521

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
        pug_id = len(self.pugs) + 1
        pug_name = "pug-{}".format(pug_id)
        temp_channel = False
        if channel is not None:
            pug = self.get_pug(channel)
            if pug is not None:
                await ctx.send("There is already an ongoing PuG in that channel.")
                return
        else:
            channel = await ctx.guild.create_text_channel(pug_name, reason="Temporary PuG channel")
            temp_channel = True
        original_channel = ctx.channel
        ctx.channel = channel
        LOG.debug("Channel is %r", channel)
        pug = Pug(ctx, self.conf, temp_channel=temp_channel)
        await self.conf.channel(channel).pug_running.set(True)
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

    # Events

    async def pug_ended(self, pug: Pug):
        """Fires when a PuG is ended, and removes it from this cog's PuGs."""
        if pug in self.pugs:
            self.pugs.remove(pug)
        await self.conf.channel(pug.ctx.channel).pug_running.set(False)

    async def pug_started(self, pug: Pug):
        """Fires when a PuG is started."""
        if pug not in self.pugs:
            self.pugs.append(pug)
        await self.conf.channel(pug.ctx.channel).pug_running.set(True)
