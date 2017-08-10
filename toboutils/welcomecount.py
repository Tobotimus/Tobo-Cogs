"""Module for WelcomeCount Cog."""
import datetime
import discord
from discord.ext import commands
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import box

UNIQUE_ID = 0x6f7951a4
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

    Idea came from Twentysix's version of Red on the official Red-DiscordBot server."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_guild(
            channel=None,
            count=0,
            day=None,
            last_message=None,
            message=_DEFAULT_WELCOME
        )

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.admin_or_permissions(manage_server=True)
    async def wcount(self, ctx: commands.Context):
        """Change settings for WelcomeCount."""
        if not ctx.invoked_subcommand:
            await self.bot.send_cmd_help(ctx)
            guild = ctx.message.guild
            settings = self.conf.guild(guild)
            channel = guild.get_channel(settings.channel())
            await ctx.send(box("Welcome channel: {0}".format(channel)))

    @wcount.command(pass_context=True)
    async def toggle(self, ctx: commands.Context):
        """Enable/disable welcome messages in this channel."""
        guild = ctx.message.guild
        channel = ctx.message.channel
        settings = self.conf.guild(guild)
        if channel.id == settings.channel():
            settings.set('channel', None)
            await ctx.send("Welcome messages are now disabled in this channel.")
        else:
            settings.set('channel', channel.id)
            await ctx.send("Welcome messages are now enabled in this channel.")

    @wcount.command(pass_context=True, no_pm=True)
    async def message(self, ctx: commands.Context, *, message: str = None):
        """Set the bot's welcome message.

        This message can be formatted using these parameters:
         mention - Mention the user who joined
         username - The user's display name
         server - The name of the server
         count - The number of users who joined today.
         plural - Empty if count is 1. 's' otherwise.
        To format the welcome message with the above parameters, include them
         in your message surrounded by curly braces {}.
        """
        guild = ctx.message.guild
        settings = self.conf.guild(guild)
        if message is None:
            await self.bot.send_cmd_help(ctx)
            await ctx.send(box(
                "Current welcome message in this guild:\n"
                "{0}".format(settings.message())
            ))
        settings.set('message', message)
        member = ctx.message.author
        count = settings.count()
        params = {
            "mention": member.mention,
            "username": member.display_name,
            "server": guild.name,
            "count": count,
            "plural": "" if count == 1 else "s"
        }
        await ctx.send("Welcome message set, sending a test message here")
        await ctx.send(message.format(**params))

    # Event
    async def on_member_join(self, member: discord.Member):
        """Send the welcome message and update the last message."""
        guild = member.guild
        settings = self.conf.guild(guild)
        today = datetime.date.today()
        if settings.day() == str(today):
            count = settings.count()
            settings.set('count', count + 1)
        else:
            settings.set('day', str(today))
            settings.set('count', 1)
            settings.set('last_message', 0)
        channel = guild.get_channel(settings.channel())
        if channel is not None:
            last_message = settings.last_message()
            if last_message is not None:
                await channel.purge_from(check=lambda m: m.id == last_message,
                                         reason="Deleting last welcome message.")
            count = settings.count()
            params = {
                "mention": member.mention,
                "username": member.display_name,
                "server": guild.name,
                "count": count,
                "plural": "s" if count > 1 else ""
            }
            welcome_msg = settings.message().format(**params)
            msg = await channel.send(welcome_msg)
            settings.set('last_message', msg.id)
