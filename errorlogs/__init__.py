"""ErrorLogs, a cog for logging command errors to a discord channel."""
from redbot.core.bot import Red
from .errorlogs import ErrorLogs


def setup(bot: Red):
    bot.add_cog(ErrorLogs())
