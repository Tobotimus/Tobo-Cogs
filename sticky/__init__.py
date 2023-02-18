"""Sticky - Sticky messages to a channel."""
import asyncio
from redbot.core.bot import Red

from .sticky import Sticky


async def setup(bot: Red):
    """Load Sticky."""
    cog = Sticky(bot)
    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
