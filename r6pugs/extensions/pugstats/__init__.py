"""Stats extension for R6Pugs."""
from .pugstats import *


def setup(bot):
    """Load PugStats"""
    bot.add_cog(PugStats())
