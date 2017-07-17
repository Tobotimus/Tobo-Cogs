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
_DEFAULT_SETTINGS = {
    "CHANNEL": None,
    "COUNT": 0,
    "DAY": None,
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
            settings = self._get_settings(server)
            channel = server.get_channel(settings["CHANNEL"])
            await self.bot.say(box("Welcome channel: {0}".format(channel)))

    @wcount.command(pass_context=True, no_pm=True)
    async def toggle(self, ctx: commands.Context):
        """Enable/disable welcome messages in this channel."""
        server = ctx.message.server
        channel = ctx.message.channel
        settings = self._get_settings(server)
        if channel.id == settings["CHANNEL"]:
            settings["CHANNEL"] = None
            await self.bot.say("Welcome messages are now disabled in this channel.")
        else:
            settings["CHANNEL"] = channel.id
            await self.bot.say("Welcome messages are now enabled in this channel.")
        self._save_settings(server, settings)

    @wcount.command(pass_context=True, no_pm=True)
    async def message(self, ctx: commands.Context, *, message: str):
        """Change what the bot says when a new user joins.

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
        settings = self._get_settings(server)
        settings["MESSAGE"] = message
        self._save_settings(server, settings)
        member = ctx.message.author
        count = settings["COUNT"]
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
        settings = self._get_settings(server)
        today = datetime.date.today()
        if settings["DAY"] == str(today):
            settings["COUNT"] += 1
        else:
            settings["DAY"] = str(today)
            settings["COUNT"] = 1
            settings["LAST_MESSAGE"] = 0
        channel = server.get_channel(settings["CHANNEL"])
        if channel is not None:
            last_message = settings.get("LAST_MESSAGE")
            if last_message is not None:
                await self.bot.purge_from(channel, check=lambda m: m.id == last_message)
            count = settings["COUNT"]
            params = {
                "mention": member.mention,
                "username": member.display_name,
                "server": server.name,
                "count": count,
                "plural": "s" if count > 1 else ""
            }
            welcome_msg = settings["MESSAGE"].format(**params)
            msg = await self.bot.send_message(channel, welcome_msg)
            settings["LAST_MESSAGE"] = msg.id
        self._save_settings(server, settings)

    def _get_settings(self, server: discord.Server):
        return self.settings.get(server.id, _DEFAULT_SETTINGS)

    def _save_settings(self, server: discord.Server, settings: dict):
        self.settings[server.id] = settings
        dataIO.save_json(_FILE_PATH, self.settings)

def _check_folders():
    if not os.path.exists(_FILE_DIR):
        os.makedirs(_FILE_DIR)

def _check_files():
    if not dataIO.is_valid_json(_FILE_PATH):
        dataIO.save_json(_FILE_PATH, {})

def setup(bot: commands.Bot):
    """Load WelcomeCount."""
    _check_folders()
    _check_files()
    bot.add_cog(WelcomeCount(bot))
