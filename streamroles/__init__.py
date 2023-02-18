"""StreamRoles - Give roles to streaming users."""
import asyncio
import logging
from redbot.core.bot import Red

from .streamroles import StreamRoles

log = logging.getLogger("red.streamroles")


async def setup(bot: Red):
    cog = StreamRoles(bot)
    await cog.initialize()

    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
