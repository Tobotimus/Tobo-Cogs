"""
This extension allows users to stay notified of PUGs starting in\
 various different ways.
"""
from core.bot import Red
from .pugnotifications import PugNotifications

def setup(bot: Red):
    """Load PugNotifications."""
    bot.add_cog(PugNotifications())
