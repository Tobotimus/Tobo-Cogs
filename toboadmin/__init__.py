"""Package for general admin plugins for V3."""
from .autorole import *
from .errorlogs import *
from .log import *


def setup(bot):
    """Load the cogs in this package."""
    bot.add_cog(Autorole())
    bot.add_cog(ErrorLogs())
