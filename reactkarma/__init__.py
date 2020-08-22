"""ReactKarma - Upvote and downvote messages to give people karma."""
from .reactkarma import ReactKarma


def setup(bot):
    bot.add_cog(ReactKarma())
