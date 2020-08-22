"""Sticky - Sticky messages to a channel."""
from .sticky import Sticky


def setup(bot):
    """Load Sticky."""
    bot.add_cog(Sticky(bot))
