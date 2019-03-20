import enum
from collections import UserString
from typing import ClassVar

from redbot.core import commands


class Scope:

    GLOBAL: ClassVar[int] = 0

    def __init__(self, value: int, name: str):
        self.value = value
        self.name = name

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> "Scope":
        argument = argument.lower()
        if argument in ("guild", "server"):
            return cls(value=ctx.guild.id, name="server")
        elif argument == "global":
            return cls(value=cls.GLOBAL, name="global")
        elif argument == "channel":
            return cls(value=ctx.channel.id, name="channel")
        else:
            raise commands.BadArgument(f"`{argument}` is an invalid scope.")


class Hideable(UserString):
    def __init__(self, *args, **kwargs) -> None:
        self.is_cog: bool = kwargs.pop("is_cog")
        super().__init__(*args, **kwargs)

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> "Hideable":
        if ctx.bot.get_cog(argument) is not None:
            return cls(argument, is_cog=True)
        command: commands.Command = ctx.bot.get_command(argument)
        if command is not None:
            return cls(command.qualified_name, is_cog=False)
        else:
            raise commands.BadArgument(
                f"`{argument}` is not a currently loaded cog or command."
            )

    @property
    def type(self) -> str:
        if self.is_cog:
            return "Cog"
        else:
            return "Command"


class EnabledState(enum.IntEnum):
    DEFAULT = -1
    DISABLED = 0
    ENABLED = 1

    # noinspection PyUnusedLocal
    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> "EnabledState":
        lowered = argument.lower()
        if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
            return cls.ENABLED
        elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
            return cls.DISABLED
        elif lowered in ("none", "clear", "default"):
            return cls.DEFAULT
        else:
            raise commands.BadArgument(
                f"`{argument}` is not a valid enabled state. Must be one of `on`, `off` "
                f"or `default`."
            )
