"""Various cogs related to Rainbow Six"""
import logging
from core.bot import Red
from .r6stats import R6Stats
from .r6pugs import R6Pugs

LOGGER = logging.getLogger('red.r6cogs')

def setup(bot: Red):
    """Loads R6Stats."""
    bot.add_cog(R6Stats(bot))
    bot.add_cog(R6Pugs(bot))
