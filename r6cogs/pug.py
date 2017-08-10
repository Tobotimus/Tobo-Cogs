"""Module for managing PuGs."""
from typing import Tuple, List, Dict
from collections import OrderedDict
import asyncio
from random import shuffle, choice
import discord
from core.utils.chat_formatting import box
from core.bot import Red
from .mappings import Maps

UNIQUE_ID = 0xd9251154

class PugManager:
    """Class to manage PuGs for a single guild."""

    def __init__(self, guild: discord.Guild, *,
                 pugs: List[Pug] = [],
                 modes: List[PugMode] = PugMode.default_modes()):
        self.guild = guild
        self.pugs = pugs
        self.modes = modes

    @classmethod
    def from_json(cls, json: Dict, guild: discord.Guild) -> cls:
        """Returns an instance of this class from the saved json settings."""
        pugs = [Pug.from_json(pug, guild) for pug in json.get('pugs')]
        modes = [PugMode.from_json(mode) for mode in json.get('modes')]
        return cls(guild,
                   pugs=pugs,
                   modes=modes)

    def to_json(self) -> Dict:
        """Get this PuG manager in JSON format."""
        if self.pugs:
            pugs = []
            for pug in self.pugs:
                pugs.append(pug.to_json())
        if self.modes:
            modes = []
            for mode in self.modes:
                modes.append(mode.to_json())
        return dict(pugs=pugs, modes=modes)

    def get_pug(self, *,
                channel: discord.Channel=None,
                pug_id: int = None) -> Pug:
        """Get a PuG either by its channel or PuG ID. Only one can be provided, else
         `ValueError` is raised.

        Returns `None` if there is no PuG running with the specified pug_id or channel."""
        if channel is not None and pug_id is not None:
            raise ValueError("Must be either `channel` or `pug_id`, not both.")
        if channel is not None:
            for pug in self.pugs:
                if pug.channel == channel:
                    return pug
            return
        elif pug_id is not None:
            try:
                pug = self.pugs[pug_id]
            except IndexError:
                return
            else:
                return pug

    def get_mode(self, mode_name: str) -> Dict:
        """Get a mode from this PuG manager. Returns `None` if it doesn't exist."""
        return next((mode for mode in self.modes if mode.name == mode_name), None)

class PugMatch:
    """Class to represent a match of a PuG."""

class CaptainsPug(Pug):
    """Class for a Pug with captains to select teams and veto maps."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_veto = MapVeto(self.map_pool)

    async def start_map_selection(self):
        """Start map selection by captains taking turns vetoing and picking."""
        self.status = super.MAP_SELECTION
        channel = self.channel
        leftover_map = self.map_veto.n_maps > self.map_veto.n_picks
        await channel.send("Map veto is starting.\nEnter one of the **bold** numbers"
                           " in the following list to veto a map!")
        header = await channel.send(str(self.map_veto))
        turn = 0
        for action in self.map_veto:
            captain = self._get_captain(0)
            await channel.send("{0.mention}'s turn to veto.")
            try:
                resp = self.bot.wait_for('message', check=self.map_veto.get_free_map,
                                         timeout=60.0)
            except asyncio.TimeoutError:
                map_ = self.map_veto.get_random()
                await channel.send("{0} took too long! I am {1}ing a random map: {2}."
                                   "".format(captain.display_name, action, Maps.get_name(map_)))
            else:
                map_ = self.map_veto.get_free_map(resp)
                await resp.delete(reason="Deleting veto message.")
                await channel.send("{0} {1}ed {2}."
                                   "".format(captain.display_name, action, Maps.get_name(map_)))
            if action == 'veto':
                self.map_veto.veto_map(map_, captain)
            elif action == 'pick':
                self.map_veto.pick_map(map_, captain)
            await header.edit(content=str(self.map_veto))
            turn = int(not turn)
        if leftover_map:
            leftover_map = self.map_veto.get_random() # Should be only 1 map left
            await channel.send("Final map will be {0}.".format(Maps.get_name(leftover_map)))
            self.map_veto.pick_map(leftover_map, None)
        self.maps = self.map_veto.maps_being_played()

    def start_team_selection(self):
        """Start selecting the teams using captain's pick."""
        self.status = super.TEAM_SELECTION
        channel = self.channel
        await channel.send("Team selection is starting. When prompted, mention the players you want to pick."
                           " Also make sure to mention the right number of players each time.")
        turn = self._get_captain(0)
        

    def _get_captain(self, team_id: int):
        teams = self.teams
        if teams and teams[team_id]:
            return teams[team_id][0]

class MapVeto:
    """Class to manage a map veto, keeping track of who vetos/picks when
     and who vetoed what.
    """

    def __init__(self, map_pool: List[str], n_maps: int = 1):
        self.data = OrderedDict()
        for map_ in map_pool:
            self.data[map_] = None
        if n_maps < 1 or n_maps > len(map_pool):
            n_maps = 1
        self.n_maps = n_maps
        self.n_picks = n_maps if n_maps % 2 == 0 else n_maps - 1
        self.n_vetoes = len(map_pool) - self.n_picks - 1

    def get_free_map(self, message: discord.Message):
        if message.content.isdigit():
            selection = int(message.content)
            try:
                map_ = self.data.keys()[selection]
            except IndexError:
                return False
            if self.data[map_] is not None:
                return False
            return True
        return False

    def get_random(self):
        return choice([map_ for map_ in self.data.keys() if self.data[map_] is None])

    def veto_map(self, map_: str, captain: discord.Member):
        """Veto a map from the pool. Raises ValueError if map is not
         in map pool.

        Returns True if the map was successfully vetoed, False if not."""
        if self.n_vetoes > 0:
            self.n_vetoes -= 1
            return self._set_map(map_, captain, 'veto')
        return False

    def pick_map(self, map_: str, captain: discord.Member):
        """Pick a map from the pool. Raises ValueError if map is not
         in map pool.

        Returns True if the map was successfully vetoed, False if not."""
        if self.n_picks > 0:
            self.n_picks -= 1
            return self._set_map(map_, captain, 'pick')
        return False

    def maps_being_played(self):
        picks = [map_ for map_ in self.data if self.data[map_][0] == 'pick']
        return sorted(picks, key=lambda m: self.data[m][2], reverse=True)

    def _set_map(self, map_: str, type_: str, captain: discord.Member):
        if map_ not in self.data:
            raise ValueError("That map is not in the map pool.")
        if self.data[map_] is not None:
            return False
        self.data[map_] = (type_, captain,
                           self.n_picks if type_ == 'pick' else self.n_vetoes)
        return True

    def __iter__(self):
        for _ in range(self.n_vetoes):
            yield 'veto'
        for _ in range(self.n_picks):
            yield 'pick'

    def __str__(self):
        def _get_lines():
            for map_, data in self.data.items():
                idx = self.data.keys().index(map_)
                map_name = Maps.get_name(map_)
                if data is None:
                    yield "**{0}.** {1}".format(idx, map_name)
                yield "~~{0}. {1}~~ *{2[0]}ed by {2[1]}*".format(idx, map_name, data)
        return "\n".join(_get_lines())

class Pug:
    """Class to represent a PuG."""
    # PuG statuses
    FILLING = 0 # PuG has less than 10 players in queue, waiting to fill up.
    READYING = 1 # PuG has at least 10 players in queue, waiting for 10 players to ready up.
    TEAM_SELECTION = 2 # PuG has 10 ready players and teams are being decided.
    MAP_SELECTION = 3 # PuG has 2 teams and maps are being selected.
    UNDERWAY = 4
    SUBMITTING = 5
    MATCH_SIZE = 10
    TEAM_SIZE = int(MATCH_SIZE / 2)

    def __init__(self, channel: discord.Channel, mode: PugMode, *,
                 role: discord.Role,
                 status: int = self.FILLING,
                 queue: List[discord.Member]=[],
                 teams: List[List[discord.Member]]=[]):
        self.channel = channel
        self.mode = mode
        self.role = role
        self.queue = queue
        self.teams = teams
        self.status = status

    @classmethod
    def from_json(cls, json: Dict, guild: discord.Guild):
        """Returns an instance of this class with the settings
         prescribed in the passed json and guild.
        """
        channel = guild.get_channel(json.get('channel'))
        mode = PugMode.from_json(json.get('mode'))
        role = discord.utils.get(guild.roles, id=json.get('role'))
        queue = [guild.get_member(member) for member in json.get('queue')]
        teams = [[guild.get_member(player) for player in team] for team in json.get('teams')]
        return cls(channel, mode,
                   role=role,
                   status=json.get('status'),
                   queue=queue,
                   teams=teams)

    def to_json(self):
        """Return this PuG in JSON format."""
        queue = [member.id for member in self.queue]
        if self.teams:
            teams = [[player.id for player in team] for team in self.teams]
        else:
            teams = []
        ret = dict(
            channel=self.channel.id,
            mode=self.mode.to_json(),
            role=self.role.id,
            status=self.status,
            queue=queue,
            teams=teams
        )
        return ret

    async def put_player(self, player: discord.Member):
        """Add a player to this PuG.

        Returns `True` if the queue was changed as a result of the call.
        Returns the result of `start_readying()` if the PuG went into
         readying up as a result."""
        if player not in self.queue + self._teams():
            self.queue.append(player)
            if self.queue.index(player) < 10:
                msg = "{0.mention} has joined the PuG!".format(player)
                if self.role not in player.roles:
                    await player.add_roles(self.role, reason=msg)
            else:
                msg = ("{0.mention} has joined the PuG at position {1} in the queue."
                       "".format(player, self.get_queue_position(player)))
            await self.channel.send(msg)
            if self.status == self.FILLING and len(self.queue) >= 10:
                return await self.start_readying()
            return True
        return False

    async def remove_player(self, player: discord.Member):
        """Remove a player from this PuG.

        Returns the team's ID if the player was kicked from a team. Returns True
         if the player was removed from the queue and not from a team.

        Raises `ValueError` if the player is not in the PuG."""
        ret = None
        msg = ''
        if player in self.queue:
            self.queue.remove(player)
            msg = "{0.mention} has been removed from the PuG.".format(player)
            ret = True
            if self.status == self.READYING and len(self.queue) < 10:
                await self.end_readying()
        elif player in self._teams():
            team_id = self.kick_player(player)
            msg = "{0.mention} has been removed from team {1}.".format(player, team_id)
            ret = team_id
        else:
            raise ValueError("That player is not in the queue or the match"
                             " for this PuG.")
        await self.channel.send(msg)
        if self.role in player.roles:
            await player.remove_roles(self.role, reason=msg)
        return ret

    def kick_player(self, player: discord.Member):
        """Kick a player from one of the teams.

        Returns the ID of the team which the player was removed from.

        Raises `ValueError` if the player is not in a team."""
        for team in self.teams:
            if player in team:
                team.remove(player)
                return self.teams.index(team)
        raise ValueError("That player is not in a team for this PuG.")

    def get_queue_position(self, player: discord.Member) -> int:
        """Get a player's position in the queue."""
        try:
            ret = self.queue.index(player) + 1
        except ValueError:
            # Check if player is in a team
            ret = None
            if player in self._teams():
                ret = 0
        return ret

    async def start_readying(self) -> Tuple[discord.Message, str]:
        """Start the readying up phase for this PuG.

        Returns a tuple with the message which players
         need to react to in order to ready up, and the
         emoji of the reaction.
        """
        assert len(self.queue) >= 10, "Not enough players to start readying up."
        self.status = self.READYING
        emoji = u'\u2705'
        msg = await self.channel.send("{0.mention} - There are enough players in this PuG"
                                      " to start the match. Click the {1} reaction below"
                                      " this message to ready up! *(You have 60 seconds)*"
                                      "".format(self.role, emoji))
        await msg.add_reaction(emoji)
        return (msg, emoji)

    async def end_readying(self):
        """End the readying up phase for this PuG as not enough players were
         ready to start a match.
        """
        self.status = self.FILLING
        await self.channel.send("Not enough players readied up and as a result less than"
                                " 10 players are left in the PuG. This PuG is going back to"
                                " waiting for players.")

    async def start_team_selection(self, bot: Red):
        """Start the team selection for this PuG."""
        if self.mode.captains_select:
            return PugMode.captains_select_teams(self, bot)
        return PugMode.random_teams(self)

    async def start_map_selection(self, bot: Red):
        """Start the Map Selection phase for this PuG.

        If maps are voted for, this method returns a tuple of the message
         which players have to vote on, the mapping from alphabet emojis
         to maps.
        """
        raise NotImplementedError()

    def start_match(self, map_: str):
        """Start a match for this PuG on the specified map.

        Queue must contain at least 10 ready players."""

    def end_match(self, score: Tuple[int] = None):
        """End a match for this PuG.

        Score is passed as `(blue team, orange team)`. If omitted,
         it assumes the match was cancelled and no score is recorded.
        """

    def list_teams(self):
        """Returns a string of the players on each team."""
        msg = "The teams for this PuG are:\n"
        col_width = max(self.teams[0], key=lambda p: len(str(p)))
        def _adjust_str(string):
            return string + " " * (col_width-len(string))
        msg += box(
            "{0} | Orange Team\n"
            "{1[0]} | {2[0]}\n"
            "{1[1]} | {2[1]}\n"
            "{1[2]} | {2[2]}\n"
            "{1[3]} | {2[3]}\n"
            "{1[4]} | {2[4]}\n"
            "".format(_adjust_str("Blue Team"),
                      [_adjust_str(str(player)) for player in self.teams[0]],
                      [str(player) for player in self.teams[1]]),
            lang='py'
        )
        return msg

    def _teams(self) -> Tuple[discord.Member]:
        """Returns a tuple of both team lists concatenated together.

        Returns `None` if teams are empty."""
        if self.teams:
            return tuple([player for player in team for team in self.teams])

class PugMode:
    """Class to keep a PuG mode's settings."""

    def __init__(self, name: str, map_pool: List[str], *,
                 veto_maps: bool = True,
                 captains_select: bool = True,
                 losers_leave: bool = False):
        self.name = name
        self.map_pool = map_pool
        self.veto_maps = veto_maps
        self.captains_select = captains_select
        self.losers_leave = losers_leave

    @staticmethod
    async def captains_select_teams(pug: Pug, bot: Red):
        """Method for selecting teams with two captains."""
        channel = pug.channel
        players = pug.queue[:10]
        shuffle(players)
        teams = pug.teams
        teams.append([players.pop(0)])
        teams.append([players.pop(0)])
        await channel.send("The captains are {0.mention} and {1.mention}.\n"
                           "To pick players, simply mention them when"
                           " prompted. You must mention the exact amount"
                           " of players which are to be picked.")
        msg = await channel.send("Players which can be picked:\n" +
                                 box("\n".join(str(player) for player in players)))
        async def _select_players(captain, players, n_picks):
            resp = await bot.wait_for('message',
                                      check=lambda m: (
                                          m.author == captain and
                                          m.channel == channel and
                                          len([p for p in players if p in m.mentions]) == n_picks))
            return [p for p in players if p in resp.mentions]
        async def _update_teams_msg(players, teams):
            msg_content = ("Players which can be picked:\n" +
                           box("\n".join(str(player) for player in players)) +
                           "\nBlue team:\n" +
                           box("\n".join(str(player) for player in teams[0])) +
                           "\nOrange team:\n" +
                           box("\n".join(str(player) for player in teams[1])))
            await msg.edit(content=msg_content)
        cur = 1
        n_picks = 1
        while players:
            if len(players) == 1:
                await channel.send("{0.mention} goes to {1.mention}'s team.")
                teams[cur].append(players.pop())
                break
            cur = int(not cur)
            captain = teams[cur][0]
            await channel.send("{0.mention}'s turn to pick {1} player(s)."
                               "".format(captain, n_picks))
            picks = await _select_players(captain, players, n_picks)
            for player in picks:
                player_idx = players.index(player)
                teams[cur].append(players.pop(player_idx))
            n_picks = 2
            await _update_teams_msg(players, teams)
        await pug.channel.send(pug.list_teams())

    @staticmethod
    async def random_teams(pug: Pug):
        """Method for selecting random teams."""
        players = pug.queue[:10]
        shuffle(players)
        pug.teams.append(players[:5])
        pug.teams.append(players[5:10])
        del pug.queue[:10]
        await pug.channel.send(pug.list_teams())

    @staticmethod
    async def vote_maps(pug: Pug, bot: Red):
        """Method for getting players to vote for the map to be played."""
        maps_list = ""
        emojis = list(map(chr, range(ord(u'\U0001F1E6'), ord(u'\U0001F1FF') + 1)))
        emojis_and_maps = zip(emojis, pug.mode.map_pool)
        for emoji, map_ in emojis_and_maps:
            maps_list += "\n{0} {1}".format(emoji,
                                            Maps.get_name(map_))
        msg = ("Here are the list of maps:"
               "{}"
               "\nTo vote for a map, click the reaction below which corresponds to the"
               " map you're voting for! The map with the most player votes will be played."
               "\nYou have 30 seconds!".format(maps_list))
        msg = await pug.channel.send(msg)
        for emoji, _ in emojis_and_maps:
            await msg.add_reaction(emoji)
        return (msg, dict(emojis_and_maps))

    @classmethod
    def default_modes(cls) -> List[cls]:
        """Get the list of default modes."""
        return [cls('default', Maps.ALL),
                cls('default-esl', Maps.ESL),
                cls('10Man', Maps.ALL,
                    veto_maps=False,
                    captains_select=False,
                    losers_leave=True),
                cls('10man-esl', Maps.ESL,
                    veto_maps=False,
                    captains_select=False,
                    losers_leave=True)]

    @classmethod
    def from_json(cls, json: Dict):
        """Returns an instance of this class from a JSON."""
        return cls(json.get('name'), json.get('map_pool'),
                   veto_maps=json.get('veto_maps'),
                   captains_select=json.get('captains_select'),
                   losers_leave=json.get('losers_leave'))

    def to_json(self):
        """Returns a this mode in JSON format."""
        return self.__dict__

    def __eq__(self, other):
        this_values = self.__dict__
        del this_values['name']
        other_values = other.__dict__
        del other_values['name']
        return this_values == other_values

    def __ne__(self, other):
        return not self.__eq__(other)
