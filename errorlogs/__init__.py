"""ErrorLogs, a cog for logging command errors to a discord channel."""
from redbot.core.bot import Red

from .errorlogs import ErrorLogs

__red_end_user_data_statement__ = "This cog does not store end user data."


def setup(bot: Red):
    bot.add_cog(ErrorLogs())
