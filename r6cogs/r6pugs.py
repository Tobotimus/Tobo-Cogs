"""Module for setting up pugs in discord."""
from typing import Tuple, List, Union
from random import choice, shuffle
import asyncio
import discord
from discord.ext.commands import Context, group, guild_only
from core import Config
from core.bot import Red
from core.utils.chat_formatting import box
from .pug import PugManager, Pug, PugMode
from .mappings import Maps
from .errors import Forbidden

UNIQUE_ID = 0xd9251154
_DEFAULT_MODES = {
    'default': {
        'mappool': Maps.ALL,
        'veto_maps': True,
        'captains': True,
        'losers_leave': False
    },
    '10man': {
        'mappool': Maps.ESL,
        'veto_maps': False,
        'captains': False,
        'losers_leave': True
    },
    '10man_allmaps': {
        'mappool': Maps.ALL,
        'veto_maps': False,
        'captains': False,
        'losers_leave': True
    },
    'captains_esl': {
        'mappool': Maps.ESL,
        'veto_maps': True,
        'captains': True,
        'losers_leave': False
    }
}
# Pug statuses
_FILLING = 0
_READYING = 1
_TEAM_SELECTION = 2
_MAP_SELECTION = 3
_UNDERWAY = 4
_SUBMITTING = 5
_MATCH_SIZE = 10
_TEAM_SIZE = int(_MATCH_SIZE / 2)

class R6Pugs:
    """Set up Rainbow Six: Siege pugs in discord!

    Some of my features will require the following permissions:
     `Manage Roles` and `Manage Channels`"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_guild(
            manager=None
        )

    @group(name='pug', aliases=['PuG', 'PUG'])
    @guild_only()
    async def pug(self, ctx: Context):
        """Start, join or manage PuGs."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            await self.send_pug_help(ctx)

    @pug.command(name='start')
    async def pug_start(self, ctx: Context,
                        mode: str = 'default', channel: discord.TextChannel=None):
        """Start a new PuG.

        <mode> is the name of the PuG mode you want to use.
        <channel> is the text channel where the pug will be run. Leave blank for the bot to
         create a temporary channel which is deleted once the pug ends.
        """
        manager = self._get_pug_manager(ctx.guild)
        await ctx.send('Pug {0} started in {1.mention}.'.format(pug_id, channel))

    @pug.command(name='join')
    async def pug_join(self, ctx: Context,
                       pug_id: int = None):
        """Join a PuG.

        If <pug_id> is omitted, it joins the PuG being run in the current channel
         (if it exists).
        """
        manager = self._get_pug_manager(ctx.guild)
        if manager is None:
            await ctx.send("There are no PuGs running in this server.")
            return
        pug = manager.get_pug(channel=ctx.channel)
        if pug_id is not None:
            pug = manager.get_pug(pug_id=pug_id)
        if pug is None:
            await ctx.send("Couldn't find the PuG you were looking for.")
            return
        prev_status = pug.status
        success = await pug.put_player(ctx.author)
        if success is False:
            await ctx.send("You are already in that PuG.")
            return
        if prev_status == Pug.FILLING and pug.status == Pug.READYING:
            await self.start_match_setup(pug)

    @pug.command(name='leave')
    async def pug_leave(self, ctx: Context):
        """Leave a PuG.

        Since you can only queue for one PuG at a time, leaves whichever
         PuG you're in.
        """

    @pug.command(name='submit')
    async def pug_submit(self, ctx: Context, points_for: int, points_against: int):
        """Submit scores for your latest PuG. Scores are accepted when a player from
         each team submits the same scores.
        """

    def _get_pug_manager(self, guild: discord.Guild) -> PugManager:
        json = self.conf.guild(guild).manager()
        if json is not None:
            return PugManager.from_json(json, guild)

    async def _save_settings(self, guild: discord.Guild):
        conf = self.conf.guild(guild)
        settings = conf.manager()
        if settings is not None:
            await conf.set('manager', settings.to_json())
            return True
        return False

    async def _ready_up(self, pug: Pug, ready_msg: discord.Message,
                        ready_emoji: Union[str, discord.Emoji]):
        while True:
            players = pug.queue[:10]
            try:
                await self.bot.wait_for(
                    'reaction_add', check=await _ready_up_check(ready_msg, players),
                    timeout=60.0)
            except asyncio.TimeoutError:
                # Update reaction
                channel = ready_msg.channel
                ready_msg = next(msg async for msg in channel.history() if msg.id == ready_msg.id)
                reaction = next(r for r in ready_msg.reactions if r.emoji == ready_emoji)
                rdy_players = [user async for user in reaction.users() if user in players]
                afk_players = list(set(players) - set(rdy_players))
                for player in afk_players:
                    await pug.remove_player(player)
                    await player.send("You were removed from a PuG in {0.name} for not readying"
                                      " up in time.".format(pug.channel.guild))
                await channel.send("Not everyone readied up; these players have been kicked for"
                                   " being AFK:\n" + "\n".join(str(p) for p in afk_players))
                if pug.status == Pug.FILLING:
                    break
                else:
                    await channel.send("The spots created by players being kicked have been filled"
                                       " by players in the queue. Everyone must ready up again!")
                    await pug.start_readying()
            else:
                await pug.start_team_selection()
                # Pug must be waiting for cog to select teams
                await self.interactive_captains_pick(pug)

    async def _select_maps(self, pug: Pug):
        result = await pug.start_map_selection()
        if isinstance(result, tuple):
            (msg, emoji_mapping) = result
            await asyncio.sleep(30.0)
            msg = next(msg_ async for msg_ in msg.channel.history() if msg_.id == msg.id)
            reactions = filter(lambda r: r.emoji in emoji_mapping, msg.reactions)
            shuffle(reactions)
            emoji = max(reactions, key=lambda r: r.count).emoji
            map_ = emoji_mapping.get(emoji)
            await pug.channel.send("{} has been selected as the map!".format(Maps.get_name(map_)))
            return map_

    async def _create_pug_role(self, guild: discord.Guild,
                               pug_id: int) -> Tuple[discord.Role]:
        role_name = 'PuG {} Player'.format(pug_id)
        reason = 'Role for pug ' + str(pug_id)
        return await guild.create_role(
            name=role_name, mentionable=True, reason=reason)

    async def _create_temp_channel(self, guild: discord.Guild, pug_id: int, *,
                                   role: discord.Role) -> discord.TextChannel:
        channel_name = 'pug_' + str(pug_id)
        reason = 'Channel for pug ' + str(pug_id)
        perms = {
            'read_messages': True,
            'send_messages': True
        }
        overwrite = {role: discord.PermissionOverwrite(**perms)}
        return await guild.create_text_channel(channel_name,
                                               overwrites=overwrite, reason=reason)

    def _available_pugs(self, ctx: Context):
        pug_channels = self.conf.guild(ctx.guild).active_pug_channels()
        for idx, channel_id in enumerate(pug_channels):
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                mode_name = self.conf.channel(channel).pug().get('mode').get('name')
                mode = self._get_mode(ctx.guild, mode_name)
                if mode.get('private'):
                    role = discord.utils.get(ctx.guild.roles, id=mode['private'])
                    if role not in ctx.author.roles:
                        continue
                yield (idx+1, mode_name, channel)

    async def send_pug_help(self, ctx: Context):
        """Send information about PuGs in the current server."""
        modes_reply = self._get_modes_help()
        pugs_reply = self._get_pugs_help(ctx)
        if modes_reply and pugs_reply:
            modes_reply += '\n'
        await ctx.send(modes_reply + pugs_reply)

    def _get_modes_help(self) -> str:
        reply = ''
        for mode in self.conf.modes():
            reply += '\n' + mode
        if reply:
            reply = 'Here are the available PuG modes:' + box(reply)
        return reply

    def _get_pugs_help(self, ctx: Context) -> str:
        reply = ''
        for pug_id, mode_name, channel in self._available_pugs(ctx):
            reply += '\n**{0}.** {1} - {2.mention}'.format(pug_id, mode_name, channel)
        if reply:
            reply = ('Here are the active PuGs on this server which {0} can join: {1}'
                     ''.format(ctx.author.display_name, reply))
        return reply

    def _get_mode(self, guild: discord.Guild, mode_name: str) -> dict:
        guild_modes = self.conf.guild(guild).modes()
        mode = guild_modes.get(mode_name)
        if mode is None:
            mode = self.conf.modes().get(mode_name)
        return mode

def _captain_pick(channel: discord.TextChannel, captain: discord.Member,
                  players: List[discord.Member], n_picks: int):
    def _pred(msg: discord.Message):
        return (_user_reply(channel, captain)(msg) and
                len(msg.mentions) in n_picks and
                msg.mentions[0] in players)
    return _pred

def _user_reply(channel: discord.TextChannel, member: discord.Member):
    def _pred(msg: discord.Message):
        return msg.author == member and msg.channel == channel
    return _pred

async def _ready_up_check(msg: discord.Message, players: List[discord.Member]):
    players = players.copy()
    def _pred(reaction: discord.Reaction, user: discord.User):
        if reaction.message == msg and reaction.emoji == '✅':
            async for user in reaction.users():
                if user in players:
                    players.remove(user)
            return bool(not players)
        return False

def _text_match_check(ctx: Context, text: str):
    def _pred(msg: discord.Message):
        return (_user_reply(ctx.channel, ctx.author)(msg) and
                msg.content.lower() == text)

def _format_team_info(teams: List[discord.Member]):
    return (
        '*Blue Team*: ' + ', '.join((player.mention for player in teams[0])) + '\n'
        '*Orange Team*: ' + ', '.join((player.mention for player in teams[1]))
    )
