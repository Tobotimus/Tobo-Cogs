"""Module for WelcomeCount Cog."""
import datetime
import os
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
            server = ctx.message.server
            channel = ctx.message.channel
            channel_settings = self._get_settings(server, channel)
            if channel_settings["ENABLED"]:
                await self.bot.say(
                    box("Enabled in this channel.\n"
                        "Welcome message: {0}".format(channel_settings["MESSAGE"])))
            else:
                await self.bot.say(box("Disabled in this channel."))

    @wcount.command(pass_context=True, no_pm=True)
    async def toggle(self, ctx: commands.Context):
        """Enable/disable welcome messages in this channel."""
        server = ctx.message.server
        channel = ctx.message.channel
        server_settings = self._get_settings(server)
        channel_settings = self._get_settings(server, channel)
        channel_settings["ENABLED"] = not channel_settings["ENABLED"]
        server_settings["CHANNELS"][channel.id] = channel_settings
        self._save_settings(server, server_settings)
        await self.bot.say("Welcome messages are now {0} in this channel."
                           "".format("enabled" if channel_settings["ENABLED"] else "disabled"))

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
        server_settings = self._get_settings(server)
        channel_settings = self._get_settings(server, channel)
        channel_settings["MESSAGE"] = message
        server_settings["CHANNELS"][channel.id] = channel_settings
        self._save_settings(server, server_settings)
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
        server_settings = self._get_settings(server)
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
            channel_settings = self._get_settings(server, channel)
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
            server_settings["CHANNELS"][channel.id] = channel_settings
        self._save_settings(server, server_settings)

    def _get_welcome_channels(self, server: discord.Server):
        settings = self._get_settings(server)
        for channel_id in settings["CHANNELS"]:
            if settings["CHANNELS"][channel_id]["ENABLED"]:
                channel = server.get_channel(channel_id)
                if channel is not None:
                    yield channel

    def _get_settings(self, server: discord.Server, channel: discord.Channel=None):
        settings = self.settings.get(server.id, _DEFAULT_SERVER_SETTINGS)
        if channel is not None:
            return settings["CHANNELS"].get(channel.id, _DEFAULT_CHANNEL_SETTINGS)
        return self.settings.get(server.id, _DEFAULT_SERVER_SETTINGS)

    def _save_settings(self, server: discord.Server, settings: dict):
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
