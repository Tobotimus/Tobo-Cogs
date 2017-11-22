import asyncio
import aiohttp
import discord
from discord.ext import commands

from redbot.core import Config, checks
from redbot.core.utils.chat_formatting import box

from .errors import *

UNIQUE_ID = 0x923476AF


class StreamRoles:
    """Give current twitch streamers in your server a role."""

    STREAMING = 1
    TWITCH_URL = "https://www.twitch.tv/"
    CHECK_DELAY = 15

    def __init__(self):
        self.conf = Config.get_conf(self, force_registration=True,
                                    identifier=UNIQUE_ID)
        self.conf.register_global(
            twitch_clientid=None
        )
        self.conf.register_guild(
            streamer_role=None,
            game_whitelist=[],
            mode="blacklist"
        )
        self.conf.register_member(
            blacklisted=False,
            whitelisted=False
        )
        self.task = None

    @classmethod
    def start(cls, bot: commands.Bot):
        """Instantiate and begin running the cog."""
        sroles = cls()
        sroles.task = bot.loop.create_task(sroles.stream_checker(bot))
        bot.loop.create_task(sroles.try_get_clientid(bot))
        return sroles

    async def try_get_clientid(self, bot: commands.Bot):
        """Tries to get the Twitch Client ID from the streams cog."""
        streams = bot.get_cog("Streams")
        if not streams or await self.conf.twitch_clientid():
            return
        token = await streams.db.tokens.get_attr("TwitchStream")
        if token:
            await self.conf.twitch_clientid.set(token)


    @commands.group()
    async def streamrole(self, ctx: commands.Context):
        """Manage settings for StreamRoles."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @streamrole.command()
    async def setmode(self, ctx: commands.Context, *, mode: str):
        """Set the filter mode to blacklist or whitelist."""
        mode = mode.lower()
        if mode not in ("blacklist", "whitelist"):
            await ctx.send("Mode must be `blacklist` or `whitelist`.")
            return
        await self.conf.guild(ctx.guild).mode.set(mode)
        await ctx.tick()

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @streamrole.group()
    async def whitelist(self, ctx: commands.Context):
        """Manage the whitelist."""
        if ctx.invoked_subcommand == self.whitelist:
            await ctx.send_help()

    @whitelist.command(name="add")
    async def white_add(self, ctx: commands.Context, *, user: discord.Member):
        """Add a member to the whitelist."""
        await self.conf.member(user).whitelisted.set(True)
        await ctx.tick()

    @whitelist.command(name="remove")
    async def white_remove(self, ctx: commands.Context, *, user: discord.Member):
        """Remove a member from the whitelist."""
        await self.conf.member(user).whitelisted.set(False)
        await ctx.tick()

    @whitelist.command(name="show")
    async def white_show(self, ctx: commands.Context):
        """Show the whitelisted members in this server."""
        whitelist = await self._get_filter_list(ctx.guild, "whitelist")
        if not whitelist:
            await ctx.send("The whitelist is empty.")
            return
        await ctx.send(box(", ".join(whitelist)))

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @streamrole.group()
    async def blacklist(self, ctx: commands.Context):
        """Manage the blacklist."""
        if ctx.invoked_subcommand == self.blacklist:
            await ctx.send_help()

    @blacklist.command(name="add")
    async def black_add(self, ctx: commands.Context, *, user: discord.Member):
        """Add a member to the blacklist."""
        await self.conf.member(user).blacklisted.set(True)
        await ctx.tick()

    @blacklist.command(name="remove")
    async def black_remove(self, ctx: commands.Context, *, user: discord.Member):
        """Remove a member from the blacklist."""
        await self.conf.member(user).blacklisted.set(False)
        await ctx.tick()

    @blacklist.command(name="show")
    async def black_show(self, ctx: commands.Context):
        """Show the blacklisted members in this server."""
        blacklist = await self._get_filter_list(ctx.guild, "blacklist")
        if not blacklist:
            await ctx.send("The blacklist is empty.")
            return
        await ctx.send(box(", ".join(blacklist)))

    async def _get_filter_list(self, guild: discord.Guild, mode: str):
        all_member_data = await self.conf.all_members(guild)
        mode = mode + "ed"
        gen_ids = (u for u, d in all_member_data.items() if d.get(mode))
        filter_list = map(lambda m: str(guild.get_member(m)), gen_ids)
        filter_list = tuple(filter(None, filter_list))
        return filter_list

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @streamrole.command()
    async def setrole(self, ctx: commands.Context, *, role: discord.Role):
        """Set the role which is given to streamers."""
        await self.conf.guild(ctx.guild).streamer_role.set(role.id)
        await ctx.send("Done. Streamers will now be given the {} role when "
                       "they go live.".format(role.name))

    @checks.is_owner()
    @streamrole.command(name="clientid")
    async def clientid(self, ctx: commands.Context, client_id: str):
        """Set the Client-ID for the Twitch API.

        To obtain your Client-ID:
         1. Follow this link: https://dev.twitch.tv/dashboard/apps/create
         2. Log in (this may redirect you to the home page, if so click on the
        above link again)
         3. Create an application. For the redirect URI, simply use
        http://localhost
         4. Obtain your Client-ID!
        """
        await self.conf.twitch_clientid.set(client_id)
        await ctx.send("Client ID set!")

    # Background Task
    async def stream_checker(self, bot: commands.Bot):
        """Find all streaming members and give them the streaming role.

        This is a background task which will loop as long as the bot is
        connected.
        """
        while not bot.is_closed():
            for guild in bot.guilds:
                try:
                    await self._run_stream_checks(guild)
                except Exception as exc:
                    print(repr(exc))
            await asyncio.sleep(self.CHECK_DELAY)

    async def _run_stream_checks(self, guild: discord.Guild):
        settings = self.conf.guild(guild)
        role = await settings.streamer_role()
        if role is not None:
            role = next((r for r in guild.roles if r.id == role), None)
            if role is None:
                return
        else:
            return
        for member in guild.members:
            has_role = role in member.roles
            stream = self._get_stream_handle(member)
            if stream and await self._is_allowed(member):
                try:
                    stream_id = await self.get_stream_id(stream)
                    data = await self.get_stream_info(stream_id)
                except StreamRolesError:
                    data = None
                if data:
                    games = await settings.game_whitelist()
                    if not games or data["game"] in games:
                        if not has_role:
                            await member.add_roles(role)
                        continue
            if has_role:
                await member.remove_roles(role)

    def _get_stream_handle(self, member: discord.Member):
        game = member.game
        if game is None or game.type != self.STREAMING:
            return
        if not game.url.startswith(self.TWITCH_URL):
            return
        return game.url.replace(self.TWITCH_URL, "")

    async def get_stream_id(self, stream: str):
        """Get a stream's ID, to be used in API requests."""
        with aiohttp.ClientSession() as session:
            url = "https://api.twitch.tv/kraken/users?login={}".format(stream)
            headers = await self._get_twitch_headers()
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(encoding='utf-8')
        if resp.status == 200:
            if not data["users"]:
                raise StreamNotFound(stream)
            result = data["users"][0]
            return result["_id"]
        if resp.status == 400:
            raise InvalidToken()
        elif resp.status == 404:
            raise StreamNotFound(stream)
        else:
            raise APIError()

    async def get_stream_info(self, stream_id: str):
        """Get info about a stream by its ID."""
        with aiohttp.ClientSession() as session:
            url = "https://api.twitch.tv/kraken/streams/{}".format(stream_id)
            headers = await self._get_twitch_headers()
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(encoding='utf-8')
        if resp.status == 200:
            if not data["stream"]:
                return
            return data["stream"]
        if resp.status == 400:
            raise InvalidToken()
        elif resp.status == 404:
            raise StreamNotFound(stream_id)
        else:
            raise APIError()

    async def _get_twitch_headers(self):
        return {
            'Client-ID': await self.conf.twitch_clientid(),
            'Accept': 'application/vnd.twitchtv.v5+json'
        }

    async def _is_allowed(self, member: discord.Member):
        mode = await self.conf.guild(member.guild).mode()
        mode = mode + "ed"
        return await self.conf.member(member).get_attr(mode)

    def __unload(self):
        if self.task is not None:
            self.task.cancel()
