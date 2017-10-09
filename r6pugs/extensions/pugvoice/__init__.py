"""Voice extension for R6Pugs.

This extension manages voice channels and moving players for R6Pugs.
"""
from .pugvoice import *


def setup(bot):
    """Load PugVoice."""
    bot.add_cog(PugVoice())
