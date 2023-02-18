"""UpdateRed - Update the bot with a command."""
import asyncio
import sys

from .updatered import UpdateRed


async def setup(bot):
    if sys.platform == "win32":
        # Executables previously renamed ".old" should be cleaned up
        UpdateRed.cleanup_old_executables()

    cog = UpdateRed()
    if asyncio.iscoroutinefunction(bot.add_cog):
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
