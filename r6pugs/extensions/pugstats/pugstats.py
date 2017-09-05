"""Module for PugStats cog."""
import discord
from core import Config
from r6pugs.r6pugs import UNIQUE_ID
from r6pugs.match import PugMatch

class PugStats:
    """An addon for R6Pugs which keeps track of stats for
     each player / server.
    """

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_member(wins=0, losses=0, map_stats={})

    async def on_pug_match_end(self, match: PugMatch):
        """Fires when a pug match ends and submits the stats for each player."""
        losing_score = min(score for score in match.final_score)
        losing_team_idx = match.final_score.index(losing_score)
        losing_team = match.teams[losing_team_idx]
        winning_team = match.teams[int(not losing_team_idx)]
        for winner, loser in zip(winning_team, losing_team):
            await self.update_stats(winner, match.map_, True)
            await self.update_stats(loser, match.map_, False)

    async def update_stats(self, player: discord.Member, map_: str, win: bool):
        """Update the stats for this player given a match's results."""
        settings = self.conf.member(player)
        if win:
            total = settings.wins
        else:
            total = settings.losses
        total_n = await total()
        await total.set(total_n + 1)
        stats = await settings.map_stats()
        if map_ not in stats:
            stats[map_] = (0, 0)
        stats[map_][int(not win)] += 1
        await settings.map_stats.set(stats)
