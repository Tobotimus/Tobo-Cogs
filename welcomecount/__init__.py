"""WelcomeCount - Welcomes users and keeps track of daily joins."""
import asyncio

from .welcomecount import WelcomeCount


async def setup(bot):
    """Load welcomecount."""
    cog = WelcomeCount()

    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
