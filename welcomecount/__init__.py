"""Welcome cog with which counts users who join."""
from .welcomecount import *


def setup(bot):
    """Load welcomecount."""
    bot.add_cog(WelcomeCount())
