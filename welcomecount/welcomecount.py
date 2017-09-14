"""Module for WelcomeCount Cog."""
import datetime
import os
from copy import deepcopy
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box

_FILE_DIR = os.path.join("data", "welcomecount")
_FILE_NAME = "count.json"
_FILE_PATH = os.path.join(_FILE_DIR, _FILE_NAME)
_DEFAULT_WELCOME = ("Welcome, {mention}, to {server}!\n\n"
                    "{count} user{plural} joined today!")
_DEFAULT_SERVER_SETTINGS = {
    "CHANNELS": {},
    "COUNT": 0,
    "DAY": None
}
_DEFAULT_CHANNEL_SETTINGS = {
    "ENABLED": False,
    "LAST_MESSAGE": None,
    "MESSAGE": _DEFAULT_WELCOME
}

class WelcomeCount:
    """Cog which welcomes users to your server and keeps count
     of how many users who have joined that day.

    Idea came from Twentysix's verson of Red on the official Red-DiscordBot server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = dataIO.load_json(_FILE_PATH)

    @commands.group(pass_context=True, no_pm=True, invoke_without_command=True)
    @checks.admin_or_permissions(manage_server=True)
    async def wcount(self, ctx: commands.Context):
        """Change settings for WelcomeCount."""
        if not ctx.invoked_subcommand:
            await self.bot.send_cmd_help(ctx)
            channel = ctx.message.channel
            channel_settings = self._load(channel=channel)
            if channel_settings["ENABLED"]:
                await self.bot.say(
                    box("Enabled in this channel.\n"
                        "Welcome message: {0}".format(channel_settings["MESSAGE"])))
            else:
                await self.bot.say(box("Disabled in this channel."))

    @wcount.command(pass_context=True, no_pm=True)
    async def toggle(self, ctx: commands.Context):
        """Enable/disable welcome messages in this channel."""
        channel = ctx.message.channel
        settings = self._load(channel=channel)
        settings["ENABLED"] = not settings["ENABLED"]
        self._save(settings, channel=channel)
        await self.bot.say("Welcome messages are now {0} in this channel."
                           "".format("enabled" if settings["ENABLED"] else "disabled"))

    @wcount.command(pass_context=True, no_pm=True)
    async def message(self, ctx: commands.Context, *, message: str):
        """Change what the bot says in this channel when a new user joins.

        This message can be formatted using these parameters:
         mention - Mention the user who joined
         username - The user's display name
         server - The name of the server
         count - The number of users who joined today.
         plural - Empty if count is 1. 's' otherwise.
        To format the welcome message with the above parameters, include them
         in your message surrounded by curly braces {}.
        """
        server = ctx.message.server
        channel = ctx.message.channel
        server_settings = self._load(server=server)
        channel_settings = self._load(channel=channel)
        channel_settings["MESSAGE"] = message
        self._save(channel_settings, channel=channel)
        member = ctx.message.author
        count = server_settings["COUNT"]
        params = {
            "mention": member.mention,
            "username": member.display_name,
            "server": server.name,
            "count": count,
            "plural": "" if count == 1 else "s"
        }
        await self.bot.say("Welcome message set, sending a test message here")
        await self.bot.say(message.format(**params))

    async def on_member_join(self, member: discord.Member):
        """Send the welcome message and update the last message."""
        server = member.server
        server_settings = self._load(server=server)
        today = datetime.date.today()
        if server_settings["DAY"] == str(today):
            server_settings["COUNT"] += 1
        else:
            server_settings["DAY"] = str(today)
            server_settings["COUNT"] = 1
            for channel_id, channel_settings in server_settings["CHANNELS"].items():
                channel_settings["LAST_MESSAGE"] = None
                server_settings["CHANNELS"][channel_id] = channel_settings
        count = server_settings["COUNT"]
        last_message = None
        for channel in self._get_welcome_channels(server):
            channel_settings = self._load(channel=channel)
            last_message = channel_settings.get("LAST_MESSAGE")
            if last_message is not None:
                await self.bot.purge_from(channel, check=lambda m: m.id == last_message)
            params = {
                "mention": member.mention,
                "username": member.display_name,
                "server": server.name,
                "count": count,
                "plural": "s" if count > 1 else ""
            }
            welcome_msg = channel_settings["MESSAGE"].format(**params)
            msg = await self.bot.send_message(channel, welcome_msg)
            channel_settings["LAST_MESSAGE"] = msg.id
            self._save(channel_settings, channel=channel)
        self._save(server_settings, server=server)

    def _get_welcome_channels(self, server: discord.Server):
        settings = self._load(server=server)
        for channel_id in settings["CHANNELS"]:
            if settings["CHANNELS"][channel_id]["ENABLED"]:
                channel = server.get_channel(channel_id)
                if channel is not None:
                    yield channel

    def _load(self, *,
              server: discord.Server=None,
              channel: discord.Channel=None):
        if channel is not None and server is None:
            server = channel.server
        settings = self.settings.get(server.id, deepcopy(_DEFAULT_SERVER_SETTINGS))
        if channel is not None:
            settings = settings["CHANNELS"].get(channel.id, deepcopy(_DEFAULT_CHANNEL_SETTINGS))
        return settings

    def _save(self, settings: dict, *,
              server: discord.Server=None,
              channel: discord.Channel=None):
        if channel is not None and server is None:
            if server is None:
                server = channel.server
            server_settings = self._load(server=server)
            server_settings["CHANNELS"][channel.id] = settings
            settings = server_settings
        if server is not None:
            print("Saving server %s" % server.id)
            self.settings[server.id] = settings
        dataIO.save_json(_FILE_PATH, self.settings)

def _check_folders():
    if not os.path.exists(_FILE_DIR):
        os.makedirs(_FILE_DIR)

def _check_files():
    if not dataIO.is_valid_json(_FILE_PATH):
        dataIO.save_json(_FILE_PATH, {})
    else: # Backwards compatibility
        settings = dataIO.load_json(_FILE_PATH)
        old_settings = ("CHANNEL", "LAST_MESSAGE", "MESSAGE")
        for server_id, server_settings in settings.items():
            if any(x in server_settings for x in ("CHANNEL", "LAST_MESSAGE", "MESSAGE")):
                (channel_id, last_message, message) = tuple(map(server_settings.pop, old_settings))
                server_settings["CHANNELS"] = {}
                server_settings["CHANNELS"][channel_id] = {
                    "ENABLED": True,
                    "LAST_MESSAGE": last_message,
                    "MESSAGE": message
                }
                settings[server_id] = server_settings
                dataIO.save_json(_FILE_PATH, settings)

def setup(bot: commands.Bot):
    """Load WelcomeCount."""
    _check_folders()
    _check_files()
    bot.add_cog(WelcomeCount(bot))
