"""Autorole, a cog for automatically applying roles to new users."""
from redbot.core.bot import Red
from .autorole import *


def setup(bot: Red):
    """Load the cogs in this package."""
    bot.add_cog(Autorole())
