"""Module for PugStats cog."""

# Copyright (c) 2017-2018 Tobotimus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import discord
from redbot.core import Config
from r6pugs import UNIQUE_ID, PugMatch

__all__ = ["PugStats"]


class PugStats:
    """Stats extension for R6Pugs.

    This extension keeps track of basic stats for each player / server.
    """

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_member(wins=0, losses=0, map_stats={})

    async def on_pug_match_end(self, match: PugMatch):
        """Event for a PUG match ending.

        Logs stats for each player in the database.
        """
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
            stats[map_] = [0, 0]
        stats[map_][int(not win)] += 1
        await settings.map_stats.set(stats)
