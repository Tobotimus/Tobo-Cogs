import enum

from redbot.core import commands


class FilterList(str, enum.Enum):
    blacklist = "blacklist"
    whitelist = "whitelist"

    def __str__(self) -> str:
        return self.name

    def as_participle(self) -> str:
        return self.name + "ed"

    # noinspection PyUnusedLocal
    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> "FilterList":
        try:
            # noinspection PyArgumentList
            return cls(argument.lower())
        except ValueError:
            raise commands.BadArgument("Mode must be `blacklist` or `whitelist`.")
