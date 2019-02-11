from typing import Iterator, Tuple

from redbot.core import Config, commands
from redbot.core.help_formatter import Help
from redbot.core.utils import async_filter

from .converters import EnabledState


class HideHelpFormatter(Help):
    def __init__(self, conf: Config) -> None:
        super().__init__()
        self.conf: Config = conf

    async def _get_options(self) -> Tuple["EnabledState", "EnabledState"]:
        show_hidden = None
        show_forbidden = None
        for scope in self._get_scope_list():
            options = await self.conf.custom("OPTIONS", scope).all()
            _show_hidden = options["show_hidden"]
            _show_forbidden = options["show_forbidden"]
            if show_hidden is None and _show_hidden != EnabledState.DEFAULT:
                show_hidden = EnabledState(_show_hidden)
            if show_forbidden is None and _show_forbidden != EnabledState.DEFAULT:
                show_forbidden = EnabledState(_show_forbidden)
            if show_hidden is not None and show_forbidden is not None:
                break
        else:
            if show_hidden is None:
                show_hidden = EnabledState(self.show_hidden)
            if show_forbidden is None:
                show_forbidden = EnabledState(self.show_check_failure)
        return show_hidden, show_forbidden

    async def filter_command_list(self):
        """Filter out commands."""
        show_hidden, show_forbidden = await self._get_options()

        async def predicate(tup: Tuple[str, commands.Command]) -> bool:
            cmd = tup[1]
            override = await self._get_override(cmd)
            if override is not None:
                return override
            if not show_hidden and cmd.hidden is True:
                return False
            if not show_forbidden and await self._can_run(cmd) is False:
                return False
            return True

        if self.is_cog():
            iterable = filter(
                lambda t: t[1].instance is self.command,
                self.context.bot.all_commands.items(),
            )
        else:
            iterable = self.command.all_commands.items()
        return await async_filter(predicate, iterable)

    async def _get_override(self, command: commands.Command) -> bool:
        to_check = []
        cog = command.instance
        if not self.is_cog() and command.parent is None and cog is not None:
            # Check cog's rules if it's a top-level command
            to_check.append(cog.__class__.__name__)
        to_check.append(command.qualified_name)
        for scope in self._get_scope_list():
            for name in to_check:
                overrides = await self.conf.custom("OVERRIDES", scope).all()
                if name in overrides["hidden"]:
                    return False
                elif name in overrides["shown"]:
                    return True

    async def _can_run(self, command: commands.Command) -> bool:
        old_state = self.context.permission_state
        try:
            return await command.can_run(self.context)
        except commands.CommandError:
            return False
        finally:
            self.context.permission_state = old_state

    def _get_scope_list(self) -> Iterator[str]:
        ctx = self.context
        scopes = [ctx.channel.id]
        if ctx.guild is not None:
            scopes.append(ctx.guild.id)
        scopes.append(0)
        return map(str, scopes)
