"""Module for PuG class."""

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

import random
from typing import Tuple, List
import discord
from .reactionmenus import (
    ConfirmationMenu,
    SingleSelectionMenu,
    PollMenu,
    TurnBasedVetoMenu,
    TurnBasedSelectionMenu,
)
from .match import PugMatch
from .log import LOG

__all__ = ["MAP_POOLS", "Pug"]

MAP_POOLS = {
    "All Maps": [
        "Bank",
        "Bartlett U.",
        "Border",
        "Chalet",
        "Club House",
        "Coastline",
        "Consulate",
        "Favelas",
        "Hereford Base",
        "House",
        "Kafe Dostoyevsky",
        "Kanal",
        "Oregon",
        "Plane",
        "Skyscraper",
        "Theme Park",
        "Yacht",
    ],
    "ESL Maps": [
        "Bank",
        "Border",
        "Chalet",
        "Club House",
        "Coastline",
        "Consulate",
        "Kafe Dostoyevsky",
        "Oregon",
        "Skyscraper",
    ],
}


class Pug:
    """Class to manage a PuG."""

    def __init__(
        self,
        bot,
        category: discord.CategoryChannel,
        channel: discord.TextChannel,
        owner: discord.Member,
        *,
        temp_channels: bool = False
    ):
        self.bot = bot
        self.category = category
        self.channel = channel
        self.owner = owner
        self.settings = {"temp_channels": temp_channels, "stopped": False}
        self.queue = []
        self.run_map_selection = None
        self.run_team_selection = None
        self.match = None
        self.match_running = False
        bot.dispatch("pug_start", self)

    def add_member(self, member: discord.Member):
        """Add a member to this PuG."""
        if member in self.queue:
            return False
        self.queue.append(member)
        self.bot.dispatch("pug_member_join", member, self)
        self.check_tenth_player()
        return len(self.queue)

    def remove_member(self, member: discord.Member):
        """Remove a member from this PuG."""
        if member not in self.queue:
            return False
        self.queue.remove(member)
        self.bot.dispatch("pug_member_remove", member, self)
        return len(self.queue)

    def check_tenth_player(self):
        """Start a match if 10 players have joined."""
        if len(self.queue) >= 10 and not self.match_running:
            self.bot.dispatch("tenth_player", self)

    async def run_initial_setup(self):
        """Set up the PuG and get its settings."""
        teamsel_options = {
            "Captains": self.run_captains_pick,
            "Random": self.get_random_teams,
        }
        mapsel_options = {"Veto": self.run_map_veto, "Vote": self.run_map_vote}
        loser_options = {"Losers Leave": True, "Losers Stay": False}
        setups = [
            (MAP_POOLS, "Which map pool will be used?", "the map pool for this PuG"),
            (
                teamsel_options,
                "How will teams be determined?",
                "the method for selecting teams",
            ),
            (
                mapsel_options,
                "How will maps be determined?",
                "the method for selecting maps",
            ),
            (
                loser_options,
                "Will losers leave or stay after a match?",
                "what happens after a match",
            ),
        ]
        results = []
        for dict_, title, option in setups:
            options = list(dict_.keys())
            menu = SingleSelectionMenu(
                self.bot,
                self.channel,
                self.owner,
                options,
                title=title,
                option_name=option,
            )
            result = await menu.run()
            if result is None:
                result = options[0]
                await menu.finish(result)
            results.append(dict_.get(result))
        self.settings["maps"] = results[0]
        self.run_team_selection = results[1]
        self.run_map_selection = results[2]
        self.settings["losers_leave"] = results[3]

    async def ready_up(self):
        """If 10 players have joined the queue, they should start readying up.

        Players who don't ready up within 60 seconds are kicked, and the PuG goes
         back into waiting mode.

        Returns a list of players who were kicked, if any.
        """
        if len(self.queue) < 10:
            return
        LOG.debug("Readying up")
        players = self.queue[:10]
        players_mentions = ", ".join((p.mention for p in players))
        await self.channel.send(
            "{} it is time to ready up for the PuG!" "".format(players_mentions)
        )
        return await self._confirm_ready(players, timeout=60.0)

    async def refill(self, n_spots: int):
        """Refill a PUG if spots open up whilst the pug is being set up."""
        if len(self.queue) < 10:
            return
        LOG.debug("Refilling %s spots", n_spots)
        players = self.queue[(10 - n_spots) : 10]
        LOG.debug(str(list(map(str, players))))
        players_mention = ", ".join((p.mention for p in players))
        await self.channel.send(
            "{} since some players were kicked, you are"
            " now able to take their place in the PUG."
            "".format(players_mention)
        )
        return await self._confirm_ready(players, timeout=60.0)

    async def _confirm_ready(self, players: List[discord.Member], **params):
        menu = ConfirmationMenu(
            self.bot,
            self.channel,
            players,
            title="Ready Up",
            action="ready up",
            **params
        )
        not_ready_players = await menu.run()
        if not_ready_players:
            for player in not_ready_players:
                self.queue.remove(player)
            members_str = ", ".join(
                (member.display_name for member in not_ready_players)
            )
            await self.channel.send(
                "Not all players readied up; these players have been kicked:\n"
                "{}".format(members_str)
            )
        return not_ready_players

    async def run_match(self):
        """Run a match for this PuG.

        This should only be called when there are at least 10 ready players in
        the queue.
        """
        if len(self.queue) < 10:
            return
        await self.channel.send("The match will start soon!")
        # try:
        teams = await self.run_team_selection()
        map_ = await self.run_map_selection(teams)
        self.match = PugMatch(self.bot, self.channel, teams, map_)

    async def run_captains_pick(self):
        """Get captains to pick the members for each team."""
        if len(self.queue) < 10:
            return
        players = self.queue[:10]
        captains = []
        for _ in range(2):
            cap = random.choice(players)
            captains.append(cap)
            players.remove(cap)
        options = {u.display_name: u for u in players}
        menu = TurnBasedSelectionMenu(
            self.bot,
            self.channel,
            captains,
            list(options.keys()),
            title="Captains pick teams",
            option_name="a player",
            selectors_name="captains",
            timeout=60.0,
        )
        teams = await menu.run()
        for team, captain in zip(teams, captains):
            team[:] = map(options.get, team)
            team.insert(0, captain)
        return teams

    async def get_random_teams(self):
        """Get random teams for this PuG."""
        if len(self.queue) < 10:
            return
        await self.channel.send("The teams are being randomised...")
        players = self.queue[:10]
        random.shuffle(players)
        teams = (players[:5], players[5:])
        return teams

    async def run_map_veto(self, teams: Tuple[List[discord.Member]]):
        """Run a map veto with this PuG's map pool."""
        captains = [team[0] for team in teams]
        menu = TurnBasedVetoMenu(
            self.bot,
            self.channel,
            captains,
            self.settings["maps"],
            title="Map veto",
            option_name="a map",
            selectors_name="captains",
            timeout=60.0,
        )
        picks = await menu.run()
        return picks.pop()

    async def run_map_vote(self, teams: Tuple[List[discord.Member]]):
        """Run a map vote with this PuG's map pool."""
        players = []
        for team in teams:
            for player in team:
                players.append(player)
        menu = PollMenu(
            self.bot,
            self.channel,
            players,
            self.settings["maps"],
            title="Vote For Maps",
            option_name="a map",
            timeout=60.0,
        )
        return await menu.run()

    def end(self):
        """End this PuG."""
        self.settings["stopped"] = True
        self.bot.dispatch("pug_end", self)
