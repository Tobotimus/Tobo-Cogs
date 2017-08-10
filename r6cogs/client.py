"""This module contains the classes which are used to communicate with
 R6DB.com, and get stats and aliases for players.
"""
from string import ascii_lowercase, digits
from collections import namedtuple
from datetime import datetime
import aiohttp
from .mappings import Platforms, Ranks, Regions, get_uplay_avatar
from .errors import HttpError, InvalidUsername, ResourceNotFound, NoStatsFound

# Mapping platform ID to R6DB platform URI path parameter
_R6DB_PLATFORMS = {
    Platforms.XBOX:         "xbox.",
    Platforms.PLAYSTATION:  "ps4.",
    Platforms.UPLAY:        ""
}

class R6DBClient:
    """Client to interface with R6DB.com via HTTP requests."""

    def __init__(self, *, app_id: str):
        headers = {
            "X-App-Id": app_id
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def search_player(self, username: str, *,
                            platform: str,
                            exact: int = 1):
        """Searches for a player from R6DB and returns their
         data as a json. Usernames are case-sensitive.

        Platform must be a valid platform ID."""
        platform = _R6DB_PLATFORMS.get(platform, '')
        permitted_chars = set(ascii_lowercase + digits + '._- ')
        if any(c not in permitted_chars for c in username.lower()):
            raise InvalidUsername('That is not a valid {username}.'
                                  ''.format(username=Platforms.get_username(platform)))
        username = username.replace(' ', '%20')
        url = ("https://{platform}r6db.com/api/v2/players/?"
               "name={username}&"
               "exact={exact}"
               "".format(platform=platform,
                         username=username.replace(' ', '%20'),
                         exact=exact))
        resp = await self.session.get(url)
        if resp.status != 200:
            raise HttpError(resp=resp, content=await resp.json())
        return await resp.json()

    async def get_extended(self, ubi_id: str, *,
                           platform: str = ''):
        """Get extended statistics for a player by their Ubisoft ID.
         Returns the extended data as a json.

        Platform must be a valid platform ID."""
        platform = _R6DB_PLATFORMS.get(platform, '')
        url = ("https://{platform}r6db.com/api/v2/players/"
               "{ubi_id}"
               "".format(platform=platform,
                         ubi_id=ubi_id))
        resp = await self.session.get(url)
        if resp.status != 200:
            raise HttpError(resp=resp, content=await resp.json())
        return await resp.json()

    async def get_fuzzy(self, username: str, *,
                        platform: str):
        """Does a fuzzy search for a player given the search term in
         `username`, and returns an array of dicts on each result with
         details which aim to discriminate between each of them.

        Only returns the top 5 results.

        Platform can be any platform name or ID."""
        platform = Platforms.get_id(platform)
        data = await self.search_player(username, platform=platform, exact=0)
        ret = []
        for player in data:
            if not player['lastPlayed'] or (
                    player['lastPlayed'].get('last_played') is None and
                    player['level'] == 0):
                continue # We don't care about players who haven't played
            player['name'] = player['aliases'].pop()['name']
            player['preview'] = []
            for idx, alias in enumerate(reversed(player['aliases'])):
                player['preview'].append(alias['name'])
                if idx >= 2:
                    break
            if player['lastPlayed'].get('last_played') is None:
                # For some reason this field is sometimes empty
                player['lastPlayed'] = None
            else:
                last_played_date = datetime.strptime(
                    player['lastPlayed'].get('last_played'),
                    "%Y-%m-%dT%H:%M:%S.%fZ")
                player['lastPlayed'] = (datetime.utcnow() - last_played_date).days
            del player['updated_at']
            ret.append(player)
        if not ret:
            raise ResourceNotFound()
        return ret

    async def get_general(self, ubi_id: str, *,
                          platform_name: str):
        """Request general player stats from R6DB. Returns the
         stats as a named tuple.

        Platform can be any platform name or ID.
        """
        platform = Platforms.get_id(platform_name)
        data = await self.get_extended(ubi_id, platform=platform)
        general = namedtuple('GeneralStats',
                             ('id name platform kills deaths '
                              'matches_won matches_lost matches_played '
                              'headshots playtime level icon_url colour'))
        stats = data['stats']['general']
        return general(
            id=ubi_id,
            name=data['aliases'][0]['name'],
            platform=platform, # Platform ID (str)
            kills=stats.get('kills'),
            deaths=stats.get('deaths'),
            matches_won=stats.get('won'),
            matches_lost=stats.get('lost'),
            matches_played=stats.get('played'),
            headshots=stats.get('headshot'),
            playtime=stats.get('timePlayed'),
            level=data.get('level'),
            icon_url=get_uplay_avatar(ubi_id),
            colour=Platforms.get_colour(platform)
        )

    async def get_ranked(self, ubi_id: str, *,
                         platform_name: str):
        """Request overall ranked player stats from R6DB. Returns the
         stats as a named tuple.

        Platform can be any platform name or ID."""
        platform = Platforms.get_id(platform_name)
        data = await self.get_extended(ubi_id, platform=platform)
        ranked = namedtuple('RankedStats',
                            ('id name platform rank region '
                             'mmr stdev kills deaths '
                             'matches_won matches_lost matches_played '
                             'playtime level icon_url colour'))
        stats = data['stats']['ranked']
        return ranked(
            id=ubi_id,
            name=data['aliases'][0]['name'],
            platform=platform, # Platform ID (str)
            kills=stats.get('kills'),
            deaths=stats.get('deaths'),
            matches_won=stats.get('won'),
            matches_lost=stats.get('lost'),
            matches_played=stats.get('played'),
            playtime=stats.get('timePlayed'),
            level=data.get('level'),
            icon_url=get_uplay_avatar(ubi_id),
            colour=Platforms.get_colour(platform)
        )

    async def get_season(self, ubi_id: str, *,
                         platform_name: str,
                         region_name: str,
                         season: int):
        """Request seasonal ranked player stats from R6DB. Returns the
         stats as a named tuple.

        Platform and region can be any name or ID. If region is None, returns
         highest ranked region stats. If season is None, gets the latest season.
        """
        platform = Platforms.get_id(platform_name)
        data = await self.get_extended(ubi_id, platform=platform)
        rank = namedtuple('SeasonStats',
                          ('id name platform rank region '
                           'mmr stdev rank_icon abandons '
                           'matches_won matches_lost '
                           'matches_played level icon_url colour'))
        name = data['aliases'][0]['name']
        rank_info = data['rank']
        stats = None
        if season:
            try:
                rank_info = data['seasonRanks'][season-1]
            except IndexError:
                raise NoStatsFound("Invalid season specified, must be between 1 and {0}"
                                   "".format(len(data['seasonRanks'])))
        if region_name:
            region = Regions.get_id(region_name)
            stats = rank_info[region]
        else:
            region = _get_best_region(rank_info)
            if region:
                stats = rank_info[region]
            else:
                raise NoStatsFound("No season {season_id} ranked stats were found for"
                                   " {username}.".format(season_id=season, username=name))
        rank_id = stats.get('rank')
        matches_won = stats.get('won')
        matches_lost = stats.get('lost')
        return rank(
            id=ubi_id,
            name=name,
            platform=platform, # Platform ID (str)
            rank=rank_id, # Rank ID (int)
            region=region, # Region ID (str)
            mmr=stats.get('skill_mean')*100,
            stdev=stats.get('skill_stdev')*100,
            rank_icon=Ranks.get_icon(rank_id),
            abandons=stats.get('abandons'),
            matches_won=matches_won,
            matches_lost=matches_lost,
            matches_played=matches_won+matches_lost,
            level=data.get('level'),
            icon_url=get_uplay_avatar(ubi_id),
            colour=Platforms.get_colour(platform)
        )

    async def get_misc(self, ubi_id: str, *,
                       platform_name: str):
        """Get miscellaneous stats for a player."""
        platform = Platforms.get_id(platform_name)
        data = await self.get_extended(ubi_id, platform=platform)
        misc = namedtuple('MiscStats',
                          ('id name platform assists '
                           'kills revives suicides gadgets '
                           'blind_kills melee_kills hotbreaches '
                           'penetration_kills level icon_url colour'))
        stats = data['stats']['general']
        return misc(
            id=ubi_id,
            name=data['aliases'][0]['name'],
            platform=platform, # Platform ID (str)
            assists=stats.get('assists'),
            kills=stats.get('kills'),
            revives=stats.get('revives'),
            suicides=stats.get('suicides'),
            gadgets=stats.get('gadgetsDestroyed'),
            blind_kills=stats.get('blindKills'),
            melee_kills=stats.get('meleeKills'),
            hotbreaches=stats.get('rappelBreaches'),
            penetration_kills=stats.get('penetrationKills'),
            level=data.get('level'),
            icon_url=get_uplay_avatar(ubi_id),
            colour=Platforms.get_colour(platform)
        )

    async def get_operator(self, ubi_id, *,
                           operator_name: str,
                           platform_name: str):
        """Get stats for a particular operator."""

def _get_best_region(rank_info):
    max_skill = 0
    max_rank = 0
    ret = None
    for region, stats in rank_info.items():
        if stats.get('wins') + stats.get('losses') == 0:
            continue
        if stats.get('skill_mean') > max_skill or stats.get('rank') > max_rank:
            max_skill = stats.get('skill_mean')
            max_rank = stats.get('rank')
            ret = region
    return ret
