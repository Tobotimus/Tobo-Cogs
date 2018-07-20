"""Module for the ErrorLogs cog."""

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

import traceback
import discord
from discord.ext import commands
from redbot.core import Config, checks
from redbot.core.utils.chat_formatting import pagify, box

__all__ = ["UNIQUE_ID", "ErrorLogs"]

UNIQUE_ID = 0xd0a3ccbf
IGNORED_COMMANDS = (
    commands.MissingRequiredArgument,
    commands.BadArgument,
    commands.DisabledCommand,
    commands.CommandNotFound,
    commands.CheckFailure,
    commands.NoPrivateMessage,
    commands.CommandOnCooldown,
)


class ErrorLogs:
    """Log tracebacks of command errors in discord channels."""

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(enabled=False, global_errors=False)

    @checks.is_owner()
    @commands.group()
    async def errorlogs(self, ctx: commands.Context):
        """Manage error logs."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            settings = self.conf.channel(ctx.channel)
            await ctx.send(
                box(
                    "Enabled in this channel: {}\n"
                    "Errors are logged from: {}".format(
                        await settings.enabled(),
                        "Everywhere"
                        if await settings.global_errors()
                        else "This server only",
                    )
                )
            )

    @errorlogs.command(name="enabled")
    async def _errorlogs_enable(self, ctx: commands.Context, true_or_false: bool):
        """Enable or disable error logging."""
        settings = self.conf.channel(ctx.channel)
        await settings.enabled.set(true_or_false)
        await ctx.send(
            "Done. Error logging is now {} in this channel.".format(
                "enabled" if true_or_false else "disabled"
            )
        )

    @errorlogs.command(name="global")
    async def _errorlogs_global(self, ctx: commands.Context, true_or_false: bool):
        """Enable or disable errors from all servers."""
        settings = self.conf.channel(ctx.channel)
        await settings.global_errors.set(true_or_false)
        await ctx.send(
            "Done. From now, {} will be logged in this channel.".format(
                "all errors" if true_or_false else "only errors in this server"
            )
        )

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Fires when a command error occurs and logs them."""
        if isinstance(error, IGNORED_COMMANDS):
            return
        all_dict = await self.conf.all_channels()
        if not all_dict:
            return
        channels, all_settings = _get_channels_and_settings(ctx, all_dict)
        if not any((channels, all_settings)):
            return
        error_title = "Exception in command `{}` ¯\\_(ツ)_/¯".format(
            ctx.command.qualified_name
        )
        log = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        channel = ctx.message.channel
        embed = discord.Embed(
            title=error_title,
            colour=discord.Colour.red(),
            timestamp=ctx.message.created_at,
        )
        embed.add_field(
            name="Invoker",
            value="{}\n({})".format(
                ctx.message.author.mention, str(ctx.message.author)
            ),
        )
        embed.add_field(name="Content", value=ctx.message.content)
        _channel_disp = (
            "Private channel"
            if isinstance(channel, discord.abc.PrivateChannel)
            else "{}\n({})".format(channel.mention, channel.name)
        )
        embed.add_field(name="Channel", value=_channel_disp)
        forbidden_msg = box(
            "Invoker: {}\n"
            "Content: {}\n"
            "Channel: {}".format(
                str(ctx.message.author), ctx.message.content, _channel_disp
            ),
            lang="md",
        )
        if isinstance(channel, discord.abc.GuildChannel):
            embed.add_field(name="Server", value=ctx.message.guild.name)
        for channel, settings in zip(channels, all_settings):
            disabled = not settings.get("enabled")
            diff_guild = not settings.get("global_errors") and (
                channel.guild is None or channel.guild.id != ctx.guild.id
            )
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
    all_settings = list(filter(lambda s: channels[all_settings.index(s)], all_settings))
    channels = list(filter(None, channels))
    if not (channels or any(s.get("enabled") for s in all_settings)):
        return None, None
    return channels, all_settings
