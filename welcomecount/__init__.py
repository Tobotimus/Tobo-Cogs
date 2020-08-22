"""WelcomeCount - Welcomes users and keeps track of daily joins."""
from .welcomecount import WelcomeCount


def setup(bot):
    """Load welcomecount."""
    bot.add_cog(WelcomeCount())
