"""Strikes - Keep track of misbehaving users."""
import asyncio

from .strikes import Strikes


async def setup(bot):
    cog = Strikes(bot)
    await cog.initialize()

    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
