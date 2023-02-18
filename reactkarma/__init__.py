"""ReactKarma - Upvote and downvote messages to give people karma."""
import asyncio
from redbot.core.bot import Red

from .reactkarma import ReactKarma


async def setup(bot: Red):
    cog = ReactKarma()
    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
