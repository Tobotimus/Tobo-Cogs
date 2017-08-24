"""Module for a PuG match."""
from typing import Tuple, List
import discord
from discord.ext import commands
from core.utils.chat_formatting import box

class PugMatch:
    """Class to represent a PuG match."""

    def __init__(self, ctx: commands.Context, teams: Tuple[List[discord.Member]], map_: str):
        self.ctx = ctx
        self.teams = teams
        self.map = map_
        self.scores = ([], [])
        self.final_score = None
        ctx.bot.dispatch("pug_match_start", self)

    async def send_summary(self):
        """Send a summary of this PuG match."""
        embed = discord.Embed(title="Match Summary",
                              description=self.ctx.channel.mention)
        embed.add_field(name="Map", value=self.map, inline=False)
        embed.add_field(name="Blue Team", value=box(self._team_str(0)))
        embed.add_field(name="Orange Team", value=box(self._team_str(1)))
        if any(l for l in self.scores):
            score = None
            if self._scores_settled():
                score = " - ".join(self.get_score())
            else:
                score = ("Still waiting on a player from each"
                         " team to enter a matching score.")
            embed.add_field(name="Score", value=score)
        await self.ctx.send(embed=embed)

    def _team_str(self, team_idx: int):
        team_str = (p.display_name for p in self.teams[team_idx])
        return box("+" + "\n+".join(team_str), lang="diff")

    def submit_score(self, score: Tuple[int], player: discord.Member):
        """Submit a score with (point for, points against)"""
        if self._scores_settled():
            return
        team = next((t for t in self.teams if player in t), None)
        if team is None:
            return
        team_idx = self.teams.index(team)
        if team_idx:
            score = score[::-1]
        self.scores[team_idx].append(score)
        if self._scores_settled():
            self.final_score = self.get_score()
            self.end_match()

    def _scores_settled(self):
        return any(s == t for s, t in zip(*self.scores))

    def get_score(self):
        """Get the score for this PuG."""
        return next((s for s, t in zip(*self.scores) if s == t), None)

    def end_match(self):
        """End this PuG match."""
        self.ctx.bot.dispatch("pug_match_end", self)
