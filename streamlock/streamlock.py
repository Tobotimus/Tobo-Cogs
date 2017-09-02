"""
The StreamLock cog is used to mute a discord channel when a
 Twitch stream goes online.

Issued by: _FFZendikar_ (https://github.com/FFZendikar)
Implemented by: _Tobotimus_ (https://github.com/Tobotimus)
"""

import os
import logging
import asyncio
import aiohttp
import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box

_DATA_DIR = os.path.join("data", "streamlock")
_DATA_FILENAME = "settings.json"
_DATA_PATH = os.path.join(_DATA_DIR, _DATA_FILENAME)
_DEFAULT_SETTINGS = {
    "CHANNELS": {},
    "STREAMS": {},
    "TOKEN": None
}
_DEFAULT_LOCK_MSG = ("https://twitch.tv/{stream} has gone online,"
                     " and this channel has been muted.")
_DEFAULT_UNLOCK_MSG = ("https://twitch.tv/{stream} has gone offline,"
                       " this channel is now unmuted.")
_DEFAULT_STREAM_SETTINGS = {
    "CHANNELS": [],
    "ID": None,
    "ONLINE": False
}
_DEFAULT_CHANNEL_SETTINGS = {
    "LOCK_MSG": _DEFAULT_LOCK_MSG,
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

    To get your twitch token, follow the instructions on this blog post:
     https://blog.twitch.tv/client-id-required-for-kraken-api-calls-afbb8e95f843
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
        if self.settings["TOKEN"] is None:
            streams_cog = bot.get_cog("Streams")
            if streams_cog is not None:
                token = streams_cog.settings.get("TWITCH_TOKEN")
                if token is not None:
                    self.settings["TOKEN"] = token
                    self._save(self.settings)

    @commands.group(pass_context=True, no_pm=True)
    async def streamlock(self, ctx: commands.Context):
        """Manage StreamLock."""
        if not ctx.invoked_subcommand:
            await self.bot.send_cmd_help(ctx)

    @streamlock.command(name="toggle", pass_context=True)
    async def streamlock_toggle(self, ctx: commands.Context, stream: str):
        """Toggle a Twitch stream locking this channel."""
        channel = ctx.message.channel
        settings = self._load(stream=stream)
        enabled = channel.id in settings["CHANNELS"]
        if enabled:
            settings["CHANNELS"].remove(channel.id)
        else:
            if self.settings["TOKEN"] is None:
                await self.bot.say("The bot owner must set the twitch Client-ID"
                                   " first by doing `{}streamlockset clientid`."
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
        await self.bot.say("*{0}* going online will {1} lock this channel."
                           "".format(stream, "no longer" if enabled else "now"))
        self._save(settings, stream=stream)

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

    async def stream_checker(self):
        """Checks all streams if they are online."""
        while self == self.bot.get_cog(self.__class__.__name__):
            for settings in self.settings["STREAMS"].values():
                name = await self.check_stream_online(settings["ID"])
                if name and settings["ONLINE"] is False:
                    self.bot.dispatch("stream_online", name)
                elif name is False and settings["ONLINE"] is True:
                    self.bot.dispatch("stream_offline", name)
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
            'Client-ID': self.settings["TOKEN"],
            'Accept': 'application/vnd.twitchtv.v5+json'
        }

    async def on_stream_online(self, stream: str):
        """Fires when a stream goes online which is linked
         to one or multiple channels.
        """
        await self._update_channels(stream)

    async def on_stream_offline(self, stream: str):
        """Fires when a stream goes offline which is linked
         to one or multiple channels.
        """
        await self._update_channels(stream, unlock=True)

    async def _update_channels(self, stream: str, unlock: bool = False):
        settings = self._load(stream=stream)
        channels = (self.bot.get_channel(id_) for id_ in settings["CHANNELS"])
        for channel in channels:
            if channel is None:
                continue
            await self.send_lock_msg(stream, channel, unlock=unlock)
            # Assuming the default role is always position 0.
            (role, overwrite) = channel.overwrites[0]
            overwrite.update(send_messages=None if unlock else False)
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
            return self.settings["CHANNELS"].get(channel.id, _DEFAULT_CHANNEL_SETTINGS)
        if stream is not None:
            return self.settings["STREAMS"].get(stream.lower(), _DEFAULT_STREAM_SETTINGS)
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
