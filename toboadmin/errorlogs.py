"""Main module for ErrorLogs cog."""
import traceback
import discord
from discord.ext import commands
from redbot.core import Config
from redbot.core.utils.chat_formatting import pagify, box

__all__ = ["UNIQUE_ID", "ErrorLogs"]

UNIQUE_ID = 0xd0a3ccbf
IGNORED_COMMANDS = (commands.MissingRequiredArgument, commands.BadArgument,
                    commands.DisabledCommand, commands.CommandNotFound,
                    commands.CheckFailure, commands.NoPrivateMessage,
                    commands.CommandOnCooldown)


class ErrorLogs:
    """Log tracebacks of command errors in discord channels."""

    def __init__(self):
        self.conf = Config.get_conf(
            self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(enabled=False, global_errors=False)

    @commands.group()
    async def errorlogs(self, ctx: commands.Context):
        """Manage error logs."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            settings = self.conf.channel(ctx.channel)
            await ctx.send(
                box("Enabled in this channel: {}\n"
                    "Errors are logged from: {}".format(
                        await settings.enabled(), "Everywhere" if await
                        settings.global_errors() else "This server only")))

    @errorlogs.command(name="enabled")
    async def _errorlogs_enable(self,
                                ctx: commands.Context,
                                true_or_false: bool):
        """Enable or disable error logging."""
        settings = self.conf.channel(ctx.channel)
        await settings.enabled.set(true_or_false)
        await ctx.send("Done. Error logging is now {} in this channel.".format(
            "enabled" if true_or_false else "disabled"))

    @errorlogs.command(name="global")
    async def _errorlogs_global(self,
                                ctx: commands.Context,
                                true_or_false: bool):
        """Enable or disable errors from all servers."""
        settings = self.conf.channel(ctx.channel)
        await settings.global_errors.set(true_or_false)
        await ctx.send("Done. From now, {} will be logged in this channel.".
                       format("all errors" if true_or_false else
                              "only errors in this server"))

    async def on_command_error(self,
                               ctx: commands.Context,
                               error: commands.CommandError):
        """Fires when a command error occurs and outputs errors to
        the right channels."""
        if isinstance(error, IGNORED_COMMANDS):
            return
        all_dict = await self.conf.all_channels()
        if not all_dict:
            return
        channels, all_settings = _get_channels_and_settings(ctx, all_dict)
        if not any((channels, all_settings)):
            return
        error_title = "Exception in command `{}` ¯\\_(ツ)_/¯".format(
            ctx.command.qualified_name)
        log = "".join(
            traceback.format_exception(
                type(error), error, error.__traceback__))
        channel = ctx.message.channel
        embed = discord.Embed(
            title=error_title,
            colour=discord.Colour.red(),
            timestamp=ctx.message.created_at)
        embed.add_field(
            name="Invoker",
            value="{}\n({})".format(ctx.message.author.mention,
                                    str(ctx.message.author)))
        embed.add_field(name="Content", value=ctx.message.content)
        _channel_disp = ("Private channel"
                         if isinstance(channel, discord.abc.PrivateChannel)
                         else "{}\n({})".format(channel.mention, channel.name))
        embed.add_field(name="Channel", value=_channel_disp)
        forbidden_msg = box(
            "Invoker: {}\n"
            "Content: {}\n"
            "Channel: {}".format(
                str(ctx.message.author), ctx.message.content, _channel_disp),
            lang="md")
        if isinstance(channel, discord.abc.GuildChannel):
            embed.add_field(name="Server", value=ctx.message.guild.name)
        for channel, settings in zip(channels, all_settings):
            disabled = not settings.get("enabled")
            diff_guild = (not settings.get("global_errors")
                          and (channel.guild is None
                               or channel.guild.id != ctx.guild.id))
            if disabled or diff_guild:
                continue
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                await channel.send(forbidden_msg)
            for page in pagify(log):
                await channel.send(box(page, lang="py"))


def _get_channels_and_settings(ctx: commands.Context, all_dict: dict):
    channels, all_settings = list(all_dict.keys()), list(all_dict.values())
    channels = list(map(ctx.bot.get_channel, map(int, channels)))
    all_settings = list(
        filter(lambda s: channels[all_settings.index(s)], all_settings))
    channels = list(filter(None, channels))
    if not (channels or any(s.get("enabled") for s in all_settings)):
        return (None, None)
    return channels, all_settings
