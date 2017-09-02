"""
The StreamLock cog is used to mute a discord channel when a
 Twitch stream goes online.

Issued by: _FFZendikar_ (https://github.com/FFZendikar)
Implemented by: _Tobotimus_ (https://github.com/Tobotimus)
"""

import os
import logging
import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box

_DATA_DIR = os.path.join("data", __name__)
_DATA_FILENAME = "settings.json"
_DATA_PATH = os.path.join(_DATA_DIR, _DATA_FILENAME)
_DEFAULT_SETTINGS = {
    "SERVER": {},
    "CHANNEL": {}
}
_DEFAULT_LOCK_MSG = ("https://twitch.tv/{stream} has gone online,"
                     " and this channel has been muted.")
_DEFAULT_UNLOCK_MSG = ("https://twitch.tv/{stream} has gone offline,"
                       " this channel is now unmuted.")
_DEFAULT_CHANNEL_SETTINGS = {
    "STREAMS": [],
    "LOCK_MSG": _DEFAULT_LOCK_MSG,
    "UNLOCK_MSG": _DEFAULT_UNLOCK_MSG
}
_DEFAULT_SERVER_SETTINGS = {}

LOG = logging.getLogger("red.streamlock")

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

    @commands.group(pass_context=True, no_pm=True)
    async def streamlock(self, ctx: commands.Context):
        """Manage StreamLock."""
        if not ctx.invoked_subcommand:
            await self.bot.send_cmd_help(ctx)

    @streamlock.command(name="toggle", pass_context=True)
    async def streamlock_toggle(self, ctx: commands.Context, stream: str):
        """Toggle a Twitch stream locking this channel."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        existing = next((s for s in settings["STREAMS"] if s.lower() == stream.lower()), None)
        if existing is not None:
            settings["STREAMS"].remove(existing)
        else:
            settings["STREAMS"].append(stream)
        await self.bot.say("*{0}* going online will {1} lock this channel."
                           "".format(stream, "now" if existing is None else "no longer"))
        self._save(settings, channel=channel)

    @streamlock.command(name="lockmsg", pass_context=True)
    async def streamlock_lockmsg(self, ctx: commands.Context, *, message: str = None):
        """Set the message for when the channel is locked."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        if message is None:
            await self.bot.send_cmd_help(ctx)
            await self.bot.say("Current message:\n{}"
                               "".format(box(settings["LOCK_MSG"])))
            return
        settings["LOCK_MSG"] = message
        await self.bot.say("Done.")
        self._save(settings, channel=channel)

    @streamlock.command(name="unlockmsg", pass_context=True)
    async def streamlock_unlockmsg(self, ctx: commands.Context, *, message: str = None):
        """Set the message for when the channel is unlocked."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        if message is None:
            await self.bot.send_cmd_help(ctx)
            await self.bot.say("Current message:\n{}"
                               "".format(box(settings["UNLOCK_MSG"])))
            return
        settings["UNLOCK_MSG"] = message
        await self.bot.say("Done.")
        self._save(settings, channel=channel)

    def _save(self, settings, *,
              server: discord.Server=None,
              channel: discord.Channel=None):
        if server is None and channel is None:
            self.settings = settings
        elif server is None:
            self.settings["CHANNEL"][channel.id] = settings
        elif channel is None:
            self.settings["SERVER"][server.id] = settings
        dataIO.save_json(_DATA_PATH, self.settings)

    def _load(self, *,
              server: discord.Server=None,
              channel: discord.Channel=None):
        if server is None and channel is None:
            return self.settings
        if server is None:
            return self.settings["CHANNEL"].get(channel.id, _DEFAULT_CHANNEL_SETTINGS)
        if channel is None:
            return self.settings["SERVER"].get(server.id, _DEFAULT_SERVER_SETTINGS)

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
    bot.add_cog(StreamLock(bot))
