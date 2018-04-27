"""Package for general admin plugins for V3."""
from redbot.core.bot import Red
from .autorole import *


def setup(bot: Red):
    """Load the cogs in this package."""
    bot.add_cog(Autorole())
