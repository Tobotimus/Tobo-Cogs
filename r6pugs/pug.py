"""Module for PuG class."""
import discord
from discord.ext import commands
from .utils import reaction_based_selection

MAP_POOLS = {
    "All Maps": ["Bank", "Bartlett U.", "Border",
                 "Chalet", "Club House", "Coastline",
                 "Consulate", "Favelas", "Hereford Base",
                 "House", "Kafe Dostoyevsky", "Kanal",
                 "Oregon", "Plane", "Skyscraper", "Yacht"],
    "ESL Maps": ["Bank", "Border", "Chalet",
                 "Club House", "Coastline", "Consulate",
                 "Kafe Dostoyevsky", "Oregon", "Skyscraper"]
}

class Pug:
    """Class to manage a PuG."""

    def __init__(self, ctx: commands.Context, *,
                 temp_channel: bool = False):
        self.ctx = ctx
        self.settings = {
            "temp_channel": temp_channel,
            "stopped": False
        }
        self.queue = []
        self.run_map_selection = None
        self.run_team_selection = None
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

    async def run_initial_setup(self):
        """Set up the PuG and get its settings."""
        # Map pool selection
        self.settings["maps"] = await reaction_based_selection(
            self.ctx, MAP_POOLS, title="Which map pool will be used?",
            option_name="the map pool for this PuG")

        options = {"Veto": self.run_map_veto,
                   "Vote": self.run_map_vote}
        self.run_map_selection = await reaction_based_selection(
            self.ctx, options, title="How will map's be determined?",
            option_name="the method for selecting a match")

        options = {"Captains": self.run_captains_pick,
                   "Random": self.get_random_teams}
        self.run_team_selection = await reaction_based_selection(
            self.ctx, options, title="How will teams be determined?",
            option_name="the method for selecting teams")

        options = {"Losers Leave": True,
                   "Losers Stay": False}
        self.settings["losers_leave"] = await reaction_based_selection(
            self.ctx, options, title="Will losers leave or stay after a match?",
            option_name="what happens after a match")

    async def run_map_veto(self):
        """Run a map veto with this PuG's map pool."""
        raise NotImplementedError()

    async def run_map_vote(self):
        """Run a map vote with this PuG's map pool."""
        raise NotImplementedError()

    async def run_captains_pick(self):
        """Get captains to pick the members for each team."""
        raise NotImplementedError()

    async def get_random_teams(self):
        """Get random teams for this PuG."""
        raise NotImplementedError()

    def end(self):
        """End this PuG."""
        self.settings["stopped"] = True
        self.ctx.bot.dispatch("pug_end", self)
