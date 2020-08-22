"""UpdateRed - Update the bot with a command."""
import sys

from .updatered import UpdateRed


def setup(bot):
    if sys.platform == "win32":
        # Executables previously renamed ".old" should be cleaned up
        UpdateRed.cleanup_old_executables()

    bot.add_cog(UpdateRed())
