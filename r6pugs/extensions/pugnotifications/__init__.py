"""Notifications extension for R6Pugs.

This extension allows users to stay notified of PUGs starting in
various different ways.
"""
from .pugnotifications import *


def setup(bot):
    """Load PugNotifications."""
    bot.add_cog(PugNotifications())
