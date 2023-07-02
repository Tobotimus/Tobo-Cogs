"""Module for the ErrorLogs cog."""
import asyncio
import contextlib
import re
import traceback
from typing import Dict, List, Tuple, Union

import discord
from redbot.core import Config, checks, commands, data_manager
from redbot.core.utils.chat_formatting import box, pagify

from .reaction_menu import LogScrollingMenu

__all__ = ["UNIQUE_ID", "ErrorLogs"]

UNIQUE_ID = 0xD0A3CCBF
IGNORED_ERRORS = (
    commands.UserInputError,
    commands.DisabledCommand,
    commands.CommandNotFound,
    commands.CheckFailure,
    commands.NoPrivateMessage,
    commands.CommandOnCooldown,
    commands.MaxConcurrencyReached,
)
LATEST_LOG_RE = re.compile(r"latest(?:-part(?P<part>\d+))?\.log")


class ErrorLogs(commands.Cog):
    """Log tracebacks of command errors in discord channels."""

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(enabled=False, global_errors=False)

        self._tasks: List[asyncio.Task] = []
        super().__init__()

    async def red_delete_data_for_user(self, **kwargs):
        pass  # Nothing needs to be done as no end user data is stored, but this function needs to exist so the data API knows that a possible deletion would have been handled.

    @checks.is_owner()
    @commands.group(autohelp=False)
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

    @errorlogs.command(name="scroll", aliases=["history"])
    async def _errorlogs_scroll(
        self, ctx: commands.Context, page_size: int = 25, num_pages: int = 15
    ):
        """Scroll through the console's history.

        __**Arguments**__
        `page_size`: (integer) The initial number of lines in each
        page.
        `num_pages`: (integer) The number of pages to read into the
        buffer.
        """
        latest_logs = []
        for path in (data_manager.core_data_path() / "logs").iterdir():
            match = LATEST_LOG_RE.match(path.name)
            if match:
                latest_logs.append(path)

        if not latest_logs:
            await ctx.send("Nothing seems to have been logged yet!")
            return

        latest_logs.sort(reverse=True)

        task = asyncio.create_task(
            LogScrollingMenu.send(ctx, latest_logs, page_size, num_pages)
        )
        task.add_done_callback(self._remove_task)
        self._tasks.append(task)

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Fires when a command error occurs and logs them."""
        if isinstance(error, IGNORED_ERRORS):
            return
        all_dict = await self.conf.all_channels()
        if not all_dict:
            return
        channels_and_settings = self._get_channels_and_settings(ctx, all_dict)
        if not channels_and_settings:
            return

        error_title = f"Exception in command `{ctx.command.qualified_name}` ¯\\_(ツ)_/¯"
        log = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        msg_url = ctx.message.jump_url
        if ctx.interaction:
            app_commands = await ctx.bot.list_enabled_app_commands()
            all_commands = {com: _id for k in app_commands.values() for com, _id in k.items()}

            parent = ctx.command.app_command.qualified_name
            command_str = f"{ctx.clean_prefix}{parent}"
            try:
                root_parent = parent.split(" ")[0]
            except IndexError:
                root_parent = parent
            if root_parent in all_commands:
                com_id = all_commands[root_parent]
                command_str = f"</{parent}:{com_id}>"

            kwargs = " ".join(f"{k}: {v}" for k, v in ctx.kwargs.items() if v is not None)
            args = " ".join(
                str(v)
                for v in ctx.args
                if v and not isinstance(v, (commands.Cog, commands.Context))
            )
            com_str = f"{command_str} {args} {kwargs}"
        else:
            com_str = ctx.message.content

        embed = discord.Embed(
            title=error_title,
            colour=discord.Colour.red(),
            timestamp=ctx.message.created_at,
            description=f">>> {com_str}",
        )
        embed.add_field(name="Invoker", value=f"{ctx.author.mention}\n{ctx.author}\n")
        embed.add_field(name="Message", value=msg_url)
        _channel_disp = (
            "{}\n({})".format(ctx.channel.mention, ctx.channel.name)
            if ctx.guild is not None
            else str(ctx.channel)
        )
        embed.add_field(name="Channel", value=_channel_disp)

        nonembed_context = f"Invoker: {ctx.author}\nContent: {ctx.message.content}\n"

        if ctx.guild is not None:
            embed.add_field(name="Server", value=ctx.guild.name)
            nonembed_context += (
                f"Channel: #{ctx.channel.name}\nServer: {ctx.guild.name}"
            )
        else:
            nonembed_context += "Channel " + str(ctx.channel)

        nonembed_message = f"{error_title} {msg_url} " + box(
            nonembed_context, lang="yaml"
        )

        for channel, settings in channels_and_settings:
            diff_guild = not settings.get("global_errors") and (
                channel.guild is None or channel.guild.id != ctx.guild.id
            )
            if diff_guild:
                continue
            if channel.permissions_for(
                getattr(channel, "guild", channel).me
            ).embed_links:
                await channel.send(embed=embed)
            else:
                await channel.send(nonembed_message)
            for page in pagify(log):
                await channel.send(box(page, lang="py"))

    def cog_unload(self):
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    def _remove_task(self, task: asyncio.Task) -> None:
        with contextlib.suppress(ValueError):
            self._tasks.remove(task)

    @staticmethod
    def _get_channels_and_settings(
        ctx: commands.Context, all_dict: Dict[int, Dict[str, bool]]
    ) -> List[Tuple[Union[discord.TextChannel, discord.DMChannel], Dict[str, bool]]]:
        ret: List[Tuple[discord.TextChannel, Dict[str, bool]]] = []
        for channel_id, channel_settings in all_dict.items():
            channel = ctx.bot.get_channel(channel_id)
            if channel is None or not channel_settings.get("enabled"):
                continue
            if not channel_settings.get("global_errors"):
                if ctx.guild != getattr(channel, "guild", ...):
                    continue
            ret.append((channel, channel_settings))
        return ret
