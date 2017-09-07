"""This extension manages voice channels and moving players
 for R6Pugs.
"""
from core.bot import Red
from .cog import PugVoice

def setup(bot: Red):
    """Load PugVoice"""
    bot.add_cog(PugVoice())
