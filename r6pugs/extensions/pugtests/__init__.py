"""Extension for testing R6Pugs."""
from .pugtests import *


def setup(bot):
    """Load this extension."""
    bot.add_cog(PugTests())
