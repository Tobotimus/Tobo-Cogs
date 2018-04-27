"""Module for a PuG match."""
from typing import Tuple, List
import discord
from redbot.core.utils.chat_formatting import box

__all__ = ["PugMatch"]


class PugMatch:
    """Class to represent a PuG match."""

    def __init__(self,
                 bot,
                 channel: discord.TextChannel,
                 teams: Tuple[List[discord.Member]],
                 map_: str):
        self.bot = bot
        self.channel = channel
        self.teams = teams
        self.map = map_
        self.scores = ([], [])
        self.final_score = None
        bot.dispatch("pug_match_start", self)

    async def send_summary(self):
        """Send a summary of this PuG match."""
        embed = discord.Embed(
            title="Match Summary", description=self.channel.mention)
        embed.add_field(name="Map", value=self.map, inline=False)
        embed.add_field(name="Blue Team", value=self._team_str(0))
        embed.add_field(name="Orange Team", value=self._team_str(1))
        if any(l for l in self.scores):
            score = None
            if self._scores_settled():
                score = " - ".join(map(str, self.get_score()))
            else:
                score = ("Still waiting on a player from each"
                         " team to enter a matching score.")
            embed.add_field(name="Score", value=score, inline=False)
        await self.channel.send(embed=embed)

    def _team_str(self, team_idx: int):
        team_str = (p.display_name for p in self.teams[team_idx])
        return box("+" + "\n+".join(team_str), lang="diff")

    def submit_score(self, score: Tuple[int], player: discord.Member):
        """Submit a player's team's score for the match.

        Parameters
        ----------
        score: Tuple[int]
            A tuple of ints in the form (rounds for, rounds against).

        """
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
        self.bot.dispatch("pug_match_end", self)

    def has_member(self, member: discord.Member):
        """Check if a member is a part of one of this match's teams."""
        return any(member in (p1, p2) for p1, p2 in zip(*self.teams))