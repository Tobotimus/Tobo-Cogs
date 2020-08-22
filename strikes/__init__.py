"""Strikes - Keep track of misbehaving users."""
from .strikes import Strikes


async def setup(bot):
    cog = Strikes(bot)
    await cog.initialize()
    bot.add_cog(cog)
