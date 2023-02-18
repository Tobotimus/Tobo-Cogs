"""ErrorLogs, a cog for logging command errors to a discord channel."""
import asyncio

from redbot.core.bot import Red

from .errorlogs import ErrorLogs

__red_end_user_data_statement__ = "This cog does not store end user data."


async def setup(bot: Red):
    cog = ErrorLogs()
    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
