"""ReactKarma - Upvote and downvote messages to give people karma!"""
from core.bot import Red
from .reactkarma import ReactKarma

def setup(bot: Red):
    """Load ReactKarma"""
    bot.add_cog(ReactKarma(bot))
