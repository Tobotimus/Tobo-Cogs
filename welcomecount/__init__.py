"""Welcome cog with which counts users who join."""
import logging
from redbot.core.bot import Red
from .welcomecount import WelcomeCount

LOGGER = logging.getLogger('red.welcomecount')

def setup(bot: Red):
    """Load welcomecount."""
    bot.add_cog(WelcomeCount(bot))
