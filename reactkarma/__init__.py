"""ReactKarma - Upvote and downvote messages to give people karma!"""
from .reactkarma import *
from .log import *

def setup(bot):
    """Load ReactKarma"""
    bot.add_cog(ReactKarma())
