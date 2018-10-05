"""FilterHelp - Broaden or narrow the help command list."""
from .filterhelp import FilterHelp


def setup(bot):
    bot.add_cog(FilterHelp(bot))
