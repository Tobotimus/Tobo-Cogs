import os
import json
import logging
import aiohttp
import r6sapi as api
import discord
from string import ascii_lowercase, digits
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from cogs.utils.chat_formatting import box, pagify
from datetime import datetime

_LOGGER = logging.getLogger('red.r6stats')
FOLDER_PATH = "data/r6stats"
SETTINGS_PATH = "{}/settings.json".format(FOLDER_PATH)
DEFAULT_SETTINGS = {}

UPLAY = 'uplay'
XBOX = 'xb1'
PLAYSTATION = 'psn'
NA = 'ncsa'
EU = 'emea'
ASIA = 'apac'
PLATFORMS = {
    "xb1":          XBOX,
    "xone":         XBOX,
    "xbone":        XBOX,
    "xbox":         XBOX,
    "xboxone":      XBOX,
    "ps":           PLAYSTATION,
    "ps4":          PLAYSTATION,
    "playstation":  PLAYSTATION,
    "uplay":        UPLAY,
    "pc":           UPLAY
}

R6DB_PLATFORMS = {
    XBOX:         "xbox.",
    PLAYSTATION:  "ps4.",
    UPLAY:        ""
}

PLATFORM_COLOURS = {
    XBOX:         discord.colour.Colour.green(),
    PLAYSTATION:  discord.colour.Colour.magenta(),
    UPLAY:        discord.colour.Colour.blue()
}

PLATFORM_USERNAMES = {
    XBOX: "Xbox Gamertag",
    PLAYSTATION: "PSN ID",
    UPLAY: "Uplay Nickname"
}

REGIONS = {
    "na":       NA,
    "us":       NA,
    "america":  NA,
    "eu":       EU,
    "europe":   EU,
    "asia":     ASIA,
    "au":       ASIA,
    "anz":      ASIA,
    "oceania":  ASIA
}

REGION_NAMES = {
    ASIA: "Asia",
    EU:   "EU",
    NA:   "NA"
}

RANKS = (
    'Unranked',
    'Copper IV', 'Copper III', 'Copper II', 'Copper I', 
    'Bronze IV', 'Bronze III', 'Bronze II', 'Bronze I',
    'Silver IV', 'Silver III', 'Silver II', 'Silver I',
    'Gold IV', 'Gold III', 'Gold II', 'Gold I',
    'Platinum III', 'Platinum II', 'Platinum I', 
    'Diamond'
)

class R6StatsError(Exception):
    """Base exception for this cog."""
    pass

class NoCredentials(R6StatsError):
    """No credentials were given."""
    pass

class InvalidCredentials(R6StatsError):
    pass

class APIError(R6StatsError):
    pass

class ResourceNotFound(R6StatsError):
    """Search had no results."""

class InvalidUsername(R6StatsError):
    """That is not a valid {platform_username}."""

class HttpError(R6StatsError):
    """HTTP data was invalid or unexpected"""
    def __init__(self, resp, content):
        self.resp = resp
        if not isinstance(content, dict):
            raise TypeError("HTTP content should be dict")
        self.content = content

    def _get_reason(self):
        """Calculate the reason for the error from the response content."""
        reason = self.resp.reason
        try:
            reason = self.content['error']['message']
        except (ValueError, KeyError, TypeError):
            pass
        return reason

    def __repr__(self):
        return '<HttpError %s "%s">' % (self.resp.status, self._get_reason())

    __str__ = __repr__

class R6Stats:
    """Get stats and information for players of Rainbow Six: Siege."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = dataIO.load_json(SETTINGS_PATH)
        self.client = R6StatsClient("Red-DiscordBot-ToboCogs")
        if "email" not in self.settings or "password" not in self.settings:
            self.auth = None
        else:
            self.auth = api.Auth(self.settings["email"], self.settings["password"])
        
    @checks.is_owner()
    @commands.command()
    async def r6auth(self, email: str, password: str):
        """Give the bot an Ubisoft account login to request stats."""
        self.settings["email"] = email
        self.settings["password"] = password
        self.auth = api.Auth(email=email, password=password)
        dataIO.save_json(SETTINGS_PATH, self.settings)
        await self.bot.say("Settings saved.")

    @commands.group(aliases=["r6s", "stats"], invoke_without_command=True, pass_context=True)
    async def r6stats(self, ctx: commands.Context, username: str, platform: str="Uplay"):
        """Overall stats for a particular player.
        
        Example: !r6s Tobotimus xbox"""
        await self.bot.send_typing(ctx.message.channel)
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_general()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            data = discord.Embed(title=username, 
                                 description="General stats. Use "
                                 "subcommands for more specific stats.")
            data.timestamp = datetime.datetime.now()
            data.colour = PLATFORM_COLOURS.get(platform)
            data.set_thumbnail(url=player.icon_url)
            ratio = ("{0:.2f}".format(player.kills / player.deaths) 
                     if player.deaths != 0 else "-.--")
            hs = ("{0:.1f}".format(player.headshots/player.kills*100) 
                  if player.kills != 0 else "--.-")
            k_d = ("{kills} - {deaths}\n".format(player.kills, player.deaths) +\
                   "(Ratio: {ratio})"
                   "".format(kills=player.kills,
                             deaths=player.deaths,
                             ratio=ratio)
                   )
            w_perc = ("{0:.1f}".format(player.matches_won/player.matches_played*100) 
                      if player.matches_played != 0 else "--.-")
            w_l = "{} - {}".format(player.matches_won, player.matches_lost)
            data.add_field(name="Kills - Deaths", value=k_d)
            data.add_field(name="Headshot %", value="{}%".format(hs))
            data.add_field(name="Wins - Losses", value=w_l)
            data.add_field(name="Win %", value="{}%".format(w_perc))
            data.add_field(name="Playtime", value="{0:.1f}H".format(player.time_played / 3600))
            data.add_field(name="Level", value=player.level)
            await self.bot.say(embed=data)

    @r6stats.command(pass_context=True)
    async def rank(self, ctx: commands.Context, username: str, platform: str="Uplay", region: str="ANZ"):
        """Ranked stats for a particular player.
        
        Example: !r6s rank Tobotimus uplay NA"""
        await self.bot.send_typing(ctx.message.channel)
        region = REGIONS.get(region.lower())
        if region is None: 
            await self.bot.say("Invalid region, please use `eu`, `na`, `asia`.")
            return
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_queues()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            rank = await player.get_rank(region)
            data = discord.Embed(title=username, 
                                 description=("Ranked stats for {} region"
                                              "".format(REGION_NAMES.get(region))))
            data.timestamp = datetime.datetime.now()
            data.colour = PLATFORM_COLOURS.get(platform)
            w_perc = ("{0:.1f}".format(rank.wins/(rank.losses+rank.wins)*100) 
                      if rank.losses+rank.wins != 0 else "--.-")
            if rank.get_bracket() != api.Rank.UNRANKED:
                data.set_thumbnail(url=rank.get_icon_url())
            rank_s = "{}\n".format(rank.rank) +\
                     "(Max: {})".format(api.Rank.RANKS[rank.max_rank])
            data.add_field(name="Rank", value=rank_s)
            mmr = "{}\n".format(int(rank.mmr)) +\
                  "(Max: {})\n".format(int(rank.max_mmr)) +\
                  "(Next Rank: {})\n".format(int(rank.next_rank_mmr)) +\
                  "(Uncertainty: {})".format(int(rank.skill_stdev * 100))
            data.add_field(name="MMR", value=mmr)
            record = ("{wins} - {losses}\n"
                      "(Abandons: {abandons})\n"
                      "(Win %: {w_perc}%)"
                      "".format(wins=rank.wins,
                                losses=rank.losses,
                                abandons=rank.abandons,
                                w_perc=w_perc))
            data.add_field(name="Wins - Losses", value=record)
            await self.bot.say(embed=data)

    @r6stats.command(aliases=["other"], pass_context=True)
    async def misc(self, ctx: commands.Context, username: str, platform: str="Uplay"):
        """Get Miscellaneous stats, including a hacker rating!
        
        Example: !r6s misc Tobotimus uplay
        The [platform] defaults to Uplay."""
        await self.bot.send_typing(ctx.message.channel)
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_general()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            data = discord.Embed(title=username, description="Miscellaneous stats.")
            data.timestamp = datetime.datetime.now()
            data.colour = PLATFORM_COLOURS.get(platform)
            data.set_thumbnail(url=player.icon_url)
            useful =  "**Assists:** {}\n".format(player.kill_assists) +\
                      "**Revives:** {}\n".format(player.revives) +\
                      "**Reinforcements:** {}".format(player.reinforcements_deployed)
            data.add_field(name="Usefulness", value=useful)
            useless = "**Suicides:** {}\n".format(player.suicides) +\
                      "**Barricades:** {}".format(player.barricades_deployed)
            data.add_field(name="Uselessness", value=useless)
            extras =  "**Gadgets Destroyed:** {}\n".format(player.gadgets_destroyed) +\
                      "**Blind Kills:** {}\n".format(player.blind_kills) +\
                      "**Melee Kills:** {}\n".format(player.melee_kills) +\
                      "**Hotbreaches:** {}".format(player.rappel_breaches)
            data.add_field(name="Extras", value=extras)
            hacker =  "**{}%**\n".format("{0:.1f}".format(player.penetration_kills/player.kills*200) if player.kills != 0 else "--.-") +\
                      "**Penetration Kills:** {}".format(player.penetration_kills)
            data.add_field(name="Hacker Rating", value=hacker)
            await self.bot.say(embed=data)

    #@r6stats.command(pass_context=True, hidden=True)
    #async def operator(self, ctx: commands.Context, username: str, operator: str, platform: str="Uplay"):
    #    """[WIP] Get a player's stats for a particular operator.

    #    Example: [p]r6s operator Tobotimus Mira PS4
    #    """

    @commands.command(pass_context=True)
    async def r6db(self, ctx: commands.Context, username: str, platform: str='Uplay', result:str=''):
        """Search a player's aliases on R6DB.
        
        [result] (optional) the index of the search result you want to retrieve."""
        await self.bot.send_typing(ctx.message.channel)
        platform = PLATFORMS.get(platform.lower())
        if platform is None:
            await self.bot.say("Invalid platform specified.")
            return
        try:
            search_results = await self.client.get_fuzzy(username, platform=platform)
        except HttpError as e:
            _LOGGER.debug(str(e))
            await self.bot.say(e._get_reason())
            return
        except InvalidUsername as e:
            _LOGGER.debug(str(e))
            await self.bot.say(e.__doc__.format(
                platform_username=PLATFORM_USERNAMES.get(platform)))
            return
        except R6StatsError as e:
            _LOGGER.debug(str(e))
            await self.bot.say(e.__doc__)
            return
        if not (result and result.isdigit() and int(result) > 0):
            while search_results:
                msg = self._format_search_results(search_results)
                await self.bot.say(msg)
                response = await self.bot.wait_for_message(
                    author=ctx.message.author, timeout=30.0)
                if response is None: return
                if not response.content.isdigit():
                    return
                result = response.content
                if result != '0' or len(search_results) <= 5:
                    break
                del search_results[:5]
        result = int(result)
        if result not in range(1, len(search_results)+1):
            if result > len(search_results): await self.bot.say("There weren't that many search results!")
            return
        player = search_results[result-1]
        if not player['aliases']:
            await self.bot.say("This player has no known aliases.")
            return
        msg = 'Here are the aliases for **{username}**:\n'.format(username=player['name'])
        alias_str = 'Date Created | Alias\n------------ | ------------'
        self._prepare_dates(player['aliases'])
        for a in reversed(player['aliases']):
            alias_str += '\n{date}   | {alias}'.format(
                date=a['created_at'], alias=a['name'])
        await self.bot.say(msg)
        for page in pagify(alias_str):
            await self.bot.say(box(page, lang='py'))

    async def request_player(self, username: str, platform: str):
        if self.auth is None:
            await self.bot.say("The owner needs to set the credentials first.\n"
                                "See: `[p]r6auth`")
            return
        platform = PLATFORMS.get(platform.lower())
        if platform is None:
            await self.bot.say("Invalid platform specified.")
            return
        player = None
        try:
            player = await self.auth.get_player(username, platform)
        except:
            await self.bot.say("Player not found!")
            return
        if player is None:
            await self.bot.say("Player not found!")
            return
        return player

    def _format_search_results(self, search_results):
        msg = '*Search results...*'
        idx = None
        for idx, player in enumerate(search_results):
            idx += 1 # We want a 1-based list
            rank_info = self._get_rank_info(player['ranks'])
            if player['lastPlayed'] is None:
                player['lastPlayed'] = '(unknown)'
            elif player['lastPlayed'] == 0:
                player['lastPlayed'] == 'Today'
            elif player['lastPlayed'] == 1:
                played['lastPlayed'] == 'Yesterday'
            else:
                player['lastPlayed'] = "%s days ago" % player['lastPlayed']
            msg += ("\n**{idx}. {name}**  | Lvl {lvl} | Rank: {rank} {region}"
                    " | Last played {last_played}"
                    "".format(idx=idx, name=player.get('name'), lvl=player.get('level'), 
                                rank=rank_info[0], region=rank_info[2], 
                                last_played=player['lastPlayed']))
            previous = '`{}`'.format("`, `".join(player['preview'])) if player['preview'] else 'None'
            msg += ("\n    *Previous aliases:* {}"
                    "".format(previous))
            if idx >= 5: break
        if len(search_results) > 5:
            msg += "\n**0.** More search results"
        msg += "\n\nEnter the number next to a search result to get more info."
        return msg
    
    def _get_rank_info(self, ranks):
        rank_name = RANKS[0]
        mmr = 0
        region_name = ''
        for region, info in ranks.items():
            if info['mmr'] == 2500 and info['rank'] == 0:
                continue
            if info['mmr'] >= mmr:
                rank_name = RANKS[int(info['rank'])]
                mmr = info['mmr']
                region_name = REGION_NAMES.get(region)
        return (rank_name, mmr, region_name)

    def _prepare_dates(self, aliases):
        for a in aliases:
            date_str = a.get('created_at')
            if date_str is None:
                a['created_at'] = "          " # Width of dd/mm/YYYY
                continue
            a['created_at'] = datetime.strptime(
                date_str, "%Y-%m-%dT%H:%M:%S.%fZ").strftime(
                    "%d/%m/%Y")

class R6StatsClient:
    """Client to interface with external databases and 
    make HTTP requests."""

    def __init__(self, app_id: str):
        headers = {
            "X-App-Id": app_id
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def get_player(self, username: str, *,
                         platform: str='', 
                         exact: int=1):
        """Requests a player from R6DB and returns their 
        data as a json. Usernames are case-sensitive."""
        permitted_chars = set(ascii_lowercase + digits + '._- ')
        if any(c not in permitted_chars for c in username.lower()):
            raise InvalidUsername()
        username = username.replace(' ', '%20')
        platform = R6DB_PLATFORMS.get(platform)
        url = ("https://{platform}r6db.com/api/v2/players/?"
               "name={username}&"
               "exact={exact}"
               "".format(platform=platform,
                         username=username.replace(' ', '%20'),
                         exact=exact))
        _LOGGER.info("Getting from %s" % url)
        resp = await self.session.get(url)
        if resp.status != 200:
            raise HttpError(resp=resp, content=await resp.json())
        return await resp.json()

    async def get_fuzzy(self, username: str, *,
                        platform: str=''):
        """Does a fuzzy search for a player given the search term in 
        `username`, and returns an array of dicts on each result with 
        details which aim to discriminate between each of them. 
        
        Only returns the top 5 results."""
        data = await self.get_player(username, platform=platform, exact=0)
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
                player['lastPlayed'] = None # For some reason this field is sometimes empty
            else:
                last_played_date = datetime.strptime(
                    player['lastPlayed'].get('last_played'), "%Y-%m-%dT%H:%M:%S.%fZ")
                player['lastPlayed'] = (datetime.utcnow() - last_played_date).days
            del player['updated_at']
            ret.append(player)
        if not ret:
            raise ResourceNotFound()
        return ret

def check_folders():
    if not os.path.exists(FOLDER_PATH):
        _LOGGER.info("Creating " + FOLDER_PATH + " folder...")
        os.makedirs(FOLDER_PATH)

def check_files():
    if not dataIO.is_valid_json(SETTINGS_PATH):
        dataIO.save_json(SETTINGS_PATH, DEFAULT_SETTINGS)

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(R6Stats(bot))