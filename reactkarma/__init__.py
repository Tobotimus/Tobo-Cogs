"""ReactKarma - Upvote and downvote messages to give people karma!"""
import logging
from core.bot import Red
from .reactkarma import ReactKarma

LOG = logging.getLogger("red.reactkarma")

def setup(bot: Red):
    """Load ReactKarma"""
    bot.add_cog(ReactKarma(bot))
