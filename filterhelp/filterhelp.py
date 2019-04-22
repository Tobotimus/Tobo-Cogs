"""Module for the FilterHelp cog."""
from typing import Optional

from redbot.core import Config, commands
from redbot.core.bot import Red

from .converters import EnabledState, Hideable, Scope
from .formatter import HideHelpFormatter

UNIQUE_ID = 0x10B231A2


class FilterHelp(commands.Cog):
    """Broaden or narrow the help command list."""

    def __init__(self, bot: Red) -> None:
        super().__init__()
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        if "init_custom" in dir(self.conf):
            self.conf.init_custom("OPTIONS", 1)
            self.conf.init_custom("OVERRIDES", 1)
        self.conf.register_custom(
            "OPTIONS",
            show_hidden=int(EnabledState.DEFAULT),
            show_forbidden=int(EnabledState.DEFAULT),
        )
        self.conf.register_custom("OVERRIDES", hidden=[], shown=[])
        self.bot = bot
        self._old_formatter = bot.formatter
        bot.formatter = HideHelpFormatter(self.conf)

    @commands.group(name="filterhelp")
    async def filterhelp(self, ctx: commands.Context):
        """Help menu filter options.

        Hidden overrides take precedence over shown overrides. Narrow
        scopes take precedence over broader ones.
        """

    @filterhelp.command(name="showhidden", usage="<yes_or_no> [scope=server]")
    async def filterhelp_showhidden(
        self,
        ctx: commands.Context,
        enabled: EnabledState,
        scope: Optional[Scope] = None,
    ):
        """Show commands which are hidden by default."""
        if scope is None:
            scope = ctx.guild.id
        await self.conf.custom("OPTIONS", str(scope)).show_hidden.set(int(enabled))
        await ctx.tick()

    @filterhelp.command(name="showforbidden", usage="<yes_or_no> [scope=server]")
    async def filterhelp_showforbidden(
        self,
        ctx: commands.Context,
        enabled: EnabledState,
        scope: Optional[Scope] = None,
    ):
        """Show commands which the user cannot run."""
        if scope is None:
            scope = ctx.guild.id
        await self.conf.custom("OPTIONS", str(scope)).show_forbidden.set(int(enabled))
        await ctx.tick()

    @filterhelp.command(name="hide", usage="<name> [scope=server]")
    async def filterhelp_hide(
        self, ctx: commands.Context, name: Hideable, scope: Optional[Scope] = None
    ):
        """Hide a command or cog explicitly."""
        if name is None:
            await ctx.send_help()
            return
        if scope is None:
            scope = ctx.guild.id
        async with self.conf.custom("OVERRIDES", str(scope)).hidden() as hidden:
            if name not in hidden:
                hidden.append(str(name))
                await ctx.send(f"{name.type} `{name}` is now hidden.")
            else:
                await ctx.send(f"{name.type} `{name}` is already hidden.")

    @filterhelp.command(name="unhide", usage="<name> [scope]")
    async def filterhelp_unhide(
        self, ctx: commands.Context, name: Hideable, scope: Optional[Scope] = None
    ):
        """Unhide a command or cog."""
        if name is None:
            await ctx.send_help()
            return
        if scope is None:
            try_scopes = [ctx.channel.id, ctx.guild.id, Scope.GLOBAL]
        else:
            try_scopes = [scope]
        for _scope in try_scopes:
            async with self.conf.custom("OVERRIDES", str(_scope)).hidden() as hidden:
                try:
                    hidden.remove(str(name))
                except ValueError:
                    continue
                else:
                    await ctx.send(f"{name.type} `{name}` is no longer hidden.")
                    break
        else:
            if scope is None:
                await ctx.send(f"{name.type} `{name}` isn't hidden.")
            else:
                await ctx.send(
                    f"{name.type} `{name}` isn't hidden in the {scope.name} scope."
                )
            return

    @filterhelp.command(name="show", usage="<name> [scope=server]")
    async def filterhelp_show(
        self, ctx: commands.Context, name: Hideable, scope: Optional[Scope] = None
    ):
        """Show a command or cog explicitly."""
        if name is None:
            await ctx.send_help()
            return
        if scope is None:
            scope = ctx.guild.id
        async with self.conf.custom("OVERRIDES", str(scope)).shown() as shown:
            if name not in shown:
                shown.append(str(name))
                await ctx.send(f"{name.type} `{name}` is now shown.")
            else:
                await ctx.send(f"{name.type} `{name}` is already shown.")

    @filterhelp.command(name="unshow", usage="<name> [scope]")
    async def filterhelp_unshow(
        self, ctx: commands.Context, name: Hideable, scope: Optional[Scope] = None
    ):
        """Unshow a command or cog."""
        if name is None:
            await ctx.send_help()
            return
        if scope is None:
            try_scopes = [ctx.channel.id, ctx.guild.id, Scope.GLOBAL]
        else:
            try_scopes = [scope]
        for _scope in try_scopes:
            async with self.conf.custom("OVERRIDES", str(_scope)).shown() as shown:
                try:
                    shown.remove(str(name))
                except ValueError:
                    continue
                else:
                    await ctx.send(f"{name.type} `{name}` is no longer shown.")
                    break
        else:
            if scope is None:
                await ctx.send(f"{name.type} `{name}` isn't shown.")
            else:
                await ctx.send(
                    f"{name.type} `{name}` isn't shown in the {scope.name} scope."
                )
            return

    def __unload(self) -> None:
        self.bot.formatter = self._old_formatter
