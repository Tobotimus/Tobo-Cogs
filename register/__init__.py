"""Register - Simplifies two SelfRole commands into one."""
from .register import Register


def setup(bot):
    bot.add_cog(Register())
