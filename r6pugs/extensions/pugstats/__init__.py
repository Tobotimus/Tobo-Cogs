"""Stats extension for R6Pugs."""
from core.bot import Red
from .pugstats import PugStats

def setup(bot: Red):
    """Load PugStats"""
    bot.add_cog(PugStats())
