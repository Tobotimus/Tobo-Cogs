"""UpdateRed - Update the bot with a command."""

from .updatered import UpdateRed


def setup(bot):
    bot.add_cog(UpdateRed(bot.loop))
