"""Module for PuG class."""
import discord
from discord.ext import commands
from core import Config

class Pug:
    """Class to manage a PuG."""

    def __init__(self, ctx: commands.Context, config: Config, *,
                 temp_channel: bool = False):
        self.ctx = ctx
        self.config = config
        self.temp_channel = temp_channel
        self.stopped = False
        self.queue = []
        ctx.bot.dispatch("pug_start", self)

    def add_member(self, member: discord.Member):
        """Add a member to this PuG."""
        if member in self.queue:
            return False
        self.queue.append(member)
        return True

    def remove_member(self, member: discord.Member):
        """Remove a member from this PuG."""
        if member not in self.queue:
            raise ValueError("Member {0} not in this PuG.".format(str(member)))
        self.queue.remove(member)
        return True

    def end(self):
        """End this PuG."""
        self.stopped = True
        self.ctx.bot.dispatch("pug_end", self)
