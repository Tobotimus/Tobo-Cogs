"""
The StreamLock cog is used to mute a discord channel when a
 Twitch stream goes online.

Issued by: _FFZendikar_ (https://github.com/FFZendikar)
Implemented by: _Tobotimus_ (https://github.com/Tobotimus)
"""

import os
import logging
import asyncio
from copy import deepcopy
import aiohttp
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box

_DATA_DIR = os.path.join("data", "streamlock")
_DATA_FILENAME = "settings.json"
_DATA_PATH = os.path.join(_DATA_DIR, _DATA_FILENAME)
_DEFAULT_SETTINGS = {
    "CHANNELS": {},
    "STREAMS": {},
    "CLIENT_ID": None
}
_DEFAULT_LOCK_MSG = ("https://twitch.tv/{stream} has gone online,"
                     " and this channel has been muted.")
_DEFAULT_UNLOCK_MSG = ("<https://twitch.tv/{stream}> has gone offline,"
                       " this channel is now unmuted.")
_DEFAULT_STREAM_SETTINGS = {
    "CHANNELS": [],
    "ID": None,
    "ONLINE": False
}
_DEFAULT_CHANNEL_SETTINGS = {
    "LOCK_MSG": _DEFAULT_LOCK_MSG,
    "LOCKED_BY": None,
    "UNLOCK_MSG": _DEFAULT_UNLOCK_MSG
}
_CHECK_DELAY = 30

LOG = logging.getLogger("red.streamlock")

class StreamLockError(Exception):
    """Base error for StreamLock."""
    pass

class InvalidToken(StreamLockError):
    """Invalid twitch token. The bot owner can set the
     twitch token using `streamlockset clientid`.
    """
    pass

class StreamNotFound(StreamLockError):
    """That stream could not be found."""
    pass

class APIError(StreamLockError):
    """Something went wrong whilst contacting the
     twitch API.
    """
    pass

class StreamLock:
    """
    StreamLock allows you to mute a discord channel upon a Twitch
     stream going online. Customisable messages can be sent to the
     channel upon it being muted.

    The word 'mute' in this context simply means the @everyone role
     having the 'Send Messages' permission being denied. Any other
     roles with this permission manually granted in this channel will
     override this setting and thus they will still be able to speak
     in the channel.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = dataIO.load_json(_DATA_PATH)
        if not self.settings["CLIENT_ID"]:
            streams_cog = bot.get_cog("Streams")
            if streams_cog is not None:
                token = streams_cog.settings.get("TWITCH_TOKEN")
                if token is not None:
                    self.settings["CLIENT_ID"] = token
                    self._save(self.settings)

    @commands.group(pass_context=True, no_pm=True)
    async def streamlock(self, ctx: commands.Context):
        """Manage StreamLock."""
        if not ctx.invoked_subcommand:
            await self.bot.send_cmd_help(ctx)

    @checks.mod_or_permissions(manage_messages=True)
    @streamlock.command(name="toggle", pass_context=True)
    async def streamlock_toggle(self, ctx: commands.Context, stream: str):
        """Toggle a Twitch stream locking this channel."""
        channel = ctx.message.channel
        settings = self._load(stream=stream)
        enabled = channel.id in settings["CHANNELS"]
        if enabled:
            channel_settings = self._load(channel=channel)
            locked = channel_settings["LOCKED_BY"]
            if locked is not None and locked.lower() == stream.lower():
                await self.unlock(channel)
                still_locked = next((name for name, sett in self.settings["STREAMS"].items()
                                     if channel.id in sett["CHANNELS"] and sett["ONLINE"]
                                     and name.lower() != stream.lower()),
                                    None)
                if still_locked is not None:
                    await self.bot.say("Since *{}* is still online, this channel will stay locked."
                                       "".format(still_locked))
                    await self.lock(channel, still_locked)
                else:
                    await self.bot.say("Unlocking channel...")
            settings["CHANNELS"].remove(channel.id)
        else:
            if self.settings["CLIENT_ID"] is None:
                await self.bot.say("The bot owner must set the twitch Client-ID"
                                   " first by doing `{}streamlock clientid`."
                                   "".format(ctx.prefix))
                return
            try:
                stream_id = await self.get_stream_id(stream)
            except StreamNotFound:
                await self.bot.say(
                    "I couldn't find the twitch channel *{}*, ensure it exists"
                    " and is spelt correctly.".format(stream))
                return
            except StreamLockError as err:
                await self.bot.say(err.__class__.__doc__)
                return
            if settings["ID"] is None:
                settings["ID"] = stream_id
            settings["CHANNELS"].append(channel.id)
            if settings["ONLINE"]:
                self.bot.dispatch("stream_online", stream)
        await self.bot.say("*{0}* going online will {1} lock this channel."
                           "".format(stream, "no longer" if enabled else "now"))
        self._save(settings, stream=stream)

    @checks.mod_or_permissions(manage_messages=True)
    @streamlock.command(name="lockmsg", pass_context=True)
    async def streamlock_lockmsg(self, ctx: commands.Context, *, message: str = None):
        """Set the message for when the channel is locked.

        Leave <message> blank to see the current message.

        To include the name of the stream in the message, simply
         use the placeholder {stream} in the message."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        if message is None:
            await self.bot.send_cmd_help(ctx)
            await self.bot.say("Current message:\n{}"
                               "".format(box(settings["LOCK_MSG"])))
            return
        settings["LOCK_MSG"] = message
        await self.bot.say("Done. Sending test message here...")
        await self.send_lock_msg("ExampleStream", channel)
        self._save(settings, channel=channel)

    @checks.mod_or_permissions(manage_messages=True)
    @streamlock.command(name="unlockmsg", pass_context=True)
    async def streamlock_unlockmsg(self, ctx: commands.Context, *, message: str = None):
        """Set the message for when the channel is unlocked.

        Leave <message> blank to see the current message.

        To include the name of the stream in the message, simply
         use the placeholder {stream} in the message."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        if message is None:
            await self.bot.send_cmd_help(ctx)
            await self.bot.say("Current message:\n{}"
                               "".format(box(settings["UNLOCK_MSG"])))
            return
        settings["UNLOCK_MSG"] = message
        await self.bot.say("Done. Sending test message here...")
        await self.send_lock_msg("ExampleStream", channel, unlock=True)
        self._save(settings, channel=channel)

    @checks.is_owner()
    @streamlock.command(name="clientid")
    async def streamlock_clientid(self, client_id: str):
        """Set the Client-ID for the Twitch API.

        To obtain your Client-ID:
         1. Follow this link: https://dev.twitch.tv/dashboard/apps/create
         2. Log in (this may redirect you to the home page, if so click on the above link again.)
         3. Create an application. For the redirect URI, simply use http://localhost
         4. Obtain your Client-ID!
        """
        self.settings["CLIENT_ID"] = client_id
        self._save(self.settings)
        await self.bot.say("Client ID set!")

    async def stream_checker(self):
        """Checks all streams if they are online."""
        while self == self.bot.get_cog(self.__class__.__name__):
            to_delete = []
            for stream, settings in self.settings["STREAMS"].items():
                name = await self.check_stream_online(settings["ID"])
                if name and settings["ONLINE"] is False:
                    LOG.debug("Stream going online %s", stream)
                    self.bot.dispatch("stream_online", name)
                elif name is False and settings["ONLINE"] is True:
                    LOG.debug("Stream going offline %s", stream)
                    self.bot.dispatch("stream_offline", stream)
                if not settings["CHANNELS"]:
                    to_delete.append(stream)
                await asyncio.sleep(1.0)
            for key in to_delete:
                self.settings["STREAMS"].pop(key, None)
                self._save(self.settings)
            await asyncio.sleep(_CHECK_DELAY)

    async def get_stream_id(self, stream: str):
        """Get a stream's ID, to be used in API requests."""
        session = aiohttp.ClientSession()
        url = "https://api.twitch.tv/kraken/users?login={}".format(stream)
        headers = self._get_twitch_headers()
        async with session.get(url, headers=headers) as resp:
            data = await resp.json(encoding='utf-8')
        await session.close()
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

    async def check_stream_online(self, stream_id):
        """Check if a twitch stream is online."""
        session = aiohttp.ClientSession()
        url = "https://api.twitch.tv/kraken/streams/{}".format(stream_id)
        headers = self._get_twitch_headers()
        async with session.get(url, headers=headers) as resp:
            data = await resp.json(encoding='utf-8')
        await session.close()
        if resp.status == 200:
            if data["stream"] is None:
                return False
            return data["stream"]["channel"]["display_name"]
        if resp.status == 400:
            raise InvalidToken()
        elif resp.status == 404:
            raise StreamNotFound(stream_id)
        else:
            raise APIError()

    def _get_twitch_headers(self):
        return {
            'Client-ID': self.settings["CLIENT_ID"],
            'Accept': 'application/vnd.twitchtv.v5+json'
        }

    async def on_stream_online(self, stream: str):
        """Fires when a stream goes online which is linked
         to one or multiple channels.
        """
        LOG.debug("Event running for %s", stream)
        settings = self._load(stream=stream)
        settings["ONLINE"] = True
        self._save(settings, stream=stream)
        await self._update_channels(stream)

    async def on_stream_offline(self, stream: str):
        """Fires when a stream goes offline which is linked
         to one or multiple channels.
        """
        LOG.debug("Event running for %s", stream)
        settings = self._load(stream=stream)
        settings["ONLINE"] = False
        self._save(settings, stream=stream)
        await self._update_channels(stream, unlock=True)

    async def _update_channels(self, stream: str, unlock: bool = False):
        settings = self._load(stream=stream)
        channels = (self.bot.get_channel(id_) for id_ in settings["CHANNELS"])
        for channel in channels:
            if channel is None:
                continue
            channel_settings = self._load(channel=channel)
            locked = bool(channel_settings["LOCKED_BY"])
            if locked and channel_settings["LOCKED_BY"].lower() != stream.lower():
                continue
            if locked and channel_settings["LOCKED_BY"].lower() == stream.lower():
                if unlock is False:
                    continue
                still_locked = next((name for name, sett in self.settings["STREAMS"].items()
                                     if channel.id in sett["CHANNELS"] and sett["ONLINE"]
                                     and name.lower() != stream.lower()),
                                    None)
                if still_locked is not None:
                    await self.bot.send_message(
                        channel,
                        ("*{}* has gone offline, however since *{}* is still online,"
                         " this channel will stay locked.".format(stream, still_locked)))
                    await self.lock(channel, still_locked)
                    continue
            await self.send_lock_msg(stream, channel, unlock=unlock)
            if unlock:
                await self.unlock(channel)
            else:
                await self.lock(channel, stream)

    async def unlock(self, channel: discord.Channel):
        """Unlock a channel."""
        settings = self._load(channel=channel)
        settings["LOCKED_BY"] = None
        self._save(settings, channel=channel)
        await self._update_overwrites(channel, unlock=True)

    async def lock(self, channel: discord.Channel, stream: str):
        """Lock a channel."""
        settings = self._load(channel=channel)
        settings["LOCKED_BY"] = stream
        self._save(settings, channel=channel)
        await self._update_overwrites(channel)

    async def _update_overwrites(self, channel: discord.Channel, *,
                                 unlock: bool = False):
        # Assuming the default role is always position 0.
        role = channel.server.default_role
        overwrite = channel.overwrites_for(role)
        overwrite.send_messages = None if unlock else False
        await self.bot.edit_channel_permissions(channel, role, overwrite)

    async def send_lock_msg(self, stream: str, channel: discord.Channel, *,
                            unlock: bool = False):
        """Send the lock/unlock message for a stream to a particular channel."""
        settings = self._load(channel=channel)
        if unlock:
            message = settings["UNLOCK_MSG"]
        else:
            message = settings["LOCK_MSG"]
        await self.bot.send_message(channel, message.format(stream=stream))

    def _save(self, settings, *,
              channel: discord.Channel=None,
              stream: str = None):
        if channel is not None:
            self.settings["CHANNELS"][channel.id] = settings
        elif stream is not None:
            self.settings["STREAMS"][stream.lower()] = settings
        dataIO.save_json(_DATA_PATH, self.settings)

    def _load(self, *,
              channel: discord.Channel=None,
              stream: str = None):
        if channel is not None:
            return self.settings["CHANNELS"].get(channel.id, deepcopy(_DEFAULT_CHANNEL_SETTINGS))
        if stream is not None:
            return self.settings["STREAMS"].get(stream.lower(), deepcopy(_DEFAULT_STREAM_SETTINGS))
        return self.settings

def _check_folders():
    if not os.path.exists(_DATA_DIR):
        LOG.debug("Creating %s folder...", _DATA_DIR)
        os.makedirs(_DATA_DIR)

def _check_files():
    if not dataIO.is_valid_json(_DATA_PATH):
        LOG.debug("Creating new %s...", _DATA_FILENAME)
        dataIO.save_json(_DATA_PATH, _DEFAULT_SETTINGS)

def setup(bot: commands.Bot):
    """Load StreamLock."""
    _check_folders()
    _check_files()
    cog = StreamLock(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(cog.stream_checker())
    bot.add_cog(cog)
