"""This module gets stats from R6DB.com and displays them in discord."""
from datetime import datetime
import r6sapi as api
import discord
from discord.ext.commands import command, group, Context
from core.bot import Red
from core.utils.chat_formatting import box, pagify
from .errors import R6Error, HttpError, InvalidUsername, NoStatsFound, ResourceNotFound
from .client import R6DBClient
from .mappings import Ranks, Regions

class R6Stats:
    """Get stats and information for players of Rainbow Six: Siege."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.client = R6DBClient(app_id="Red-DiscordBot-ToboCogs")

    @group(aliases=["r6s"], invoke_without_command=True)
    async def r6stats(self, ctx: Context,
                      username: str, platform: str = "Uplay"):
        """Overall stats for a particular player.

        Example: !r6s Tobotimus xbox"""
        with ctx.typing():
            search_results = await self.get_search_results(ctx, username, platform)
        player = await self.interactive_search(ctx, search_results, more_info='general stats')
        if player:
            with ctx.typing():
                general = await self.client.get_general(player['id'], platform_name=platform)
                data = discord.Embed(title=general.name,
                                     description="General stats.",
                                     timestamp=ctx.message.created_at,
                                     colour=general.colour)
                data.set_thumbnail(url=general.icon_url)
                ratio = ("{0:.2f}".format(general.kills / general.deaths)
                         if general.deaths != 0 else "-.--")
                hs_perc = ("{0:.1f}".format(general.headshots/general.kills*100)
                           if general.kills != 0 else "--.-")
                k_d = ("{kills} - {deaths}\n"
                       "(Ratio: {ratio})"
                       "".format(kills=general.kills,
                                 deaths=general.deaths,
                                 ratio=ratio))
                w_perc = (
                    "{0:.1f}".format(
                        general.matches_won / general.matches_played * 100)
                    if general.matches_played != 0 else "--.-")
                w_l = "{} - {}".format(general.matches_won, general.matches_lost)
                data.add_field(name="Kills - Deaths", value=k_d)
                data.add_field(name="Headshot %", value="{}%".format(hs_perc))
                data.add_field(name="Wins - Losses", value=w_l)
                data.add_field(name="Win %", value="{}%".format(w_perc))
                data.add_field(name="Playtime", value=(
                    "{0:.1f}H".format(general.playtime / 3600)))
                data.add_field(name="Level", value=general.level)
                await ctx.send(embed=data)

    @r6stats.command()
    async def season(self, ctx: Context, username: str,
                     platform: str = "Uplay",
                     region: str = "ANZ", *,
                     season: int = None):
        """Ranked stats for a particular player.

        Example: !r6s rank Tobotimus uplay NA"""
        with ctx.typing():
            search_results = await self.get_search_results(ctx, username, platform)
            player = self.interactive_search(ctx, search_results, more_info='ranked stats')
            if player:
                try:
                    rank = await self.client.get_season(
                        player['id'], platform_name=platform, region_name=region, season=season)
                except NoStatsFound as err:
                    ctx.send(err.args[0])
                    return
                data = discord.Embed(
                    title=username,
                    description=("Ranked stats for {} region"
                                 "".format(Regions.get_name(rank.region))),
                    colour=rank.colour,
                    timestamp=ctx.message.created_at)
                data.set_thumbnail(url=rank.rank_icon)
                w_perc = ("{0:.1f}".format(
                    rank.wins/(rank.losses+rank.wins)*100)
                          if rank.losses+rank.wins != 0 else "--.-")
                rank_s = ("{rank_name}\n"
                          "(Max: {max})"
                          "".format(rank_name=rank.rank,
                                    max=api.Rank.RANKS[rank.max_rank]))
                data.add_field(name="Rank", value=rank_s)
                mmr = ("{mmr}\n"
                       "(Max: {max_mmr})\n"
                       "(Next Rank: {next_mmr})\n"
                       "(Uncertainty: {stdev})"
                       "".format(mmr=int(rank.mmr),
                                 max_mmr=int(rank.max_mmr),
                                 next_mmr=int(rank.next_rank_mmr),
                                 stdev=int(rank.skill_stdev * 100)))
                data.add_field(name="MMR", value=mmr)
                record = ("{wins} - {losses}\n"
                          "(Abandons: {abandons})\n"
                          "(Win %: {w_perc}%)"
                          "".format(wins=rank.wins,
                                    losses=rank.losses,
                                    abandons=rank.abandons,
                                    w_perc=w_perc))
                data.add_field(name="Wins - Losses", value=record)
                await ctx.send(embed=data)

    @r6stats.command(aliases=["other"], pass_context=True)
    async def misc(self, ctx: Context,
                   username: str, platform: str = "Uplay"):
        """Get Miscellaneous stats, including a hacker rating!

        Example: !r6s misc Tobotimus uplay
        The [platform] defaults to Uplay."""
        await ctx.typing()
        search_results = await self.get_search_results(ctx, username, platform)
        player = await self.interactive_search(ctx, search_results, more_info='miscellaneous stats')
        if player:
            misc = self.client.get_misc(player['id'], platform_name=platform)
            data = discord.Embed(title=misc.name,
                                 description="Miscellaneous stats.",
                                 timestamp=ctx.message.created_at,
                                 colour=misc.colour)
            data.set_thumbnail(url=misc.icon_url)
            useful = ("**Assists:** {assists}\n"
                      "**Revives:** {revives}\n"
                      "".format(assists=misc.assists,
                                revives=misc.revives))
            data.add_field(name="Usefulness", value=useful)
            useless = ("**Suicides:** {suicides}\n"
                       "".format(suicides=misc.suicides))
            data.add_field(name="Uselessness", value=useless)
            extras = ("**Gadgets Destroyed:** {gadgets}\n"
                      "**Blind Kills:** {blind}\n"
                      "**Melee Kills:** {melee}\n"
                      "**Hotbreaches:** {hbreach}"
                      "".format(gadgets=misc.gadgets,
                                blind=misc.blind_kills,
                                melee=misc.melee_kills,
                                hbreach=misc.hotbreaches))
            data.add_field(name="Extras", value=extras)
            hacker_rating = ("{0:.1f}".format(
                misc.penetration_kills/misc.kills*200)
                             if misc.kills != 0 else "--.-")
            hacker = ("**{rating}%**\n"
                      "**Penetration Kills:** {penetration}"
                      "".format(rating=hacker_rating,
                                penetration=misc.penetration_kills))
            data.add_field(name="Hacker Rating", value=hacker)
            await ctx.send(embed=data)

    @command()
    async def r6db(self, ctx: Context, username: str,
                   platform: str = 'Uplay'):
        """Search a player's aliases on R6DB."""
        await ctx.typing()
        search_results = await self.get_search_results(ctx, username, platform)
        player = await self.interactive_search(ctx, search_results, more_info='all aliases')
        if not player['aliases']:
            await ctx.send("This player has no known aliases.")
            return
        msg = 'Here are the aliases for **{username}**:\n'.format(
            username=player['name'])
        alias_str = 'Date Created | Alias\n------------ | ------------'
        _prepare_dates(player['aliases'])
        for alias in reversed(player['aliases']):
            alias_str += '\n{date}   | {alias}'.format(
                date=alias['created_at'], alias=alias['name'])
        await ctx.send(msg)
        for page in pagify(alias_str):
            await ctx.send(box(page, lang='py'))

    async def get_search_results(self, ctx: Context, username: str, platform: str):
        """Get search results from R6DB."""
        try:
            search_results = await self.client.get_fuzzy(
                username, platform=platform)
        except ResourceNotFound:
            await ctx.send(ResourceNotFound.__doc__)
        except HttpError as err:
            await ctx.send(err.get_reason())
        except InvalidUsername as err:
            await ctx.send(err.args[0])
        except R6Error as err:
            await ctx.send(err.__doc__)
        else:
            return search_results

    async def interactive_search(self, ctx: Context, search_results: list, *,
                                 more_info: str):
        """Do an interactive R6DB search with the user."""
        result = None
        while search_results:
            msg = _format_search_results(search_results)
            msg += ("\n\nEnter the number next to a search result to get"
                    " {more_info} for that player.".format(more_info=more_info))
            await ctx.send(msg)
            response = await self.bot.wait_for(
                'message', check=_reply_msg_pred(ctx), timeout=30.0)
            if response is None:
                return
            if not response.content.isdigit():
                return
            result = int(response.content)
            if result not in range(len(search_results)+1):
                return
            if result == 0 and len(search_results) <= 5:
                return
            if result != 0 or len(search_results) <= 5:
                break
            del search_results[:5]
        return search_results[result-1]

def _format_search_results(search_results):
    msg = '*Search results...*'
    idx = None
    for idx, player in enumerate(search_results):
        idx += 1 # We want a 1-based list
        rank_info = _get_rank_info(player['ranks'])
        if player['lastPlayed'] is None:
            player['lastPlayed'] = '(unknown)'
        elif player['lastPlayed'] == 0:
            player['lastPlayed'] = 'Today'
        elif player['lastPlayed'] == 1:
            player['lastPlayed'] = 'Yesterday'
        else:
            player['lastPlayed'] = "{} days ago".format(
                player['lastPlayed'])
        msg += ("\n**{idx}. {name}**  | Lvl {lvl} | "
                "Rank: {rank} {region}"
                " | Last played {last_played}"
                "".format(idx=idx, name=player.get('name'),
                          lvl=player.get('level'),
                          rank=rank_info[0], region=rank_info[2],
                          last_played=player['lastPlayed']))
        previous = ('`{}`'.format("`, `".join(player['preview']))
                    if player['preview'] else 'None')
        msg += ("\n    *Previous aliases:* {}"
                "".format(previous))
        if idx >= 5:
            break
    if len(search_results) > 5:
        msg += "\n**0.** More search results"
    return msg

def _get_rank_info(ranks):
    rank_name = Ranks.get_name(0)
    mmr = 0
    region_name = ''
    for region, info in ranks.items():
        if info['mmr'] == 2500 and info['rank'] == 0:
            continue
        if info['mmr'] >= mmr:
            rank_name = Ranks.get_name(int(info['rank']))
            mmr = info['mmr']
            region_name = Regions.get_name(region)
    return (rank_name, mmr, region_name)

def _prepare_dates(aliases):
    for alias in aliases:
        date_str = alias.get('created_at')
        if date_str is None:
            alias['created_at'] = "          " # Width of dd/mm/YYYY
            continue
        alias['created_at'] = datetime.strptime(
            date_str, "%Y-%m-%dT%H:%M:%S.%fZ").strftime(
                "%d/%m/%Y")

def _reply_msg_pred(ctx: Context):
    """Returns a predicate which checks whether a message is a direct response
     to the bot."""
    def _pred(msg: discord.Message):
        return msg.author == ctx.author and msg.channel == ctx.channel
    return _pred

def setup(bot):
    """Load this cog."""
    bot.add_cog(R6Stats(bot))
