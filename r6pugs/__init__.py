"""Package for R6Pugs."""
from core.bot import Red
from .r6pugs import R6Pugs

def setup(bot: Red):
    """Load R6Pugs"""
    cog = R6Pugs()
    bot.add_cog(R6Pugs())
