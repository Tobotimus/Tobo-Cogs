"""Extension for testing R6Pugs."""
from redbot.core.bot import Red
from .pugtests import PugTests

def setup(bot: Red):
    """Load this extension."""
    bot.add_cog(PugTests())
