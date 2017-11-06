"""Module for WelcomeCount Cog."""
import datetime
import discord
from discord.ext import commands
from redbot.core import checks, Config
from redbot.core.utils.chat_formatting import box

__all__ = ["UNIQUE_ID", "WelcomeCount"]

UNIQUE_ID = 0x6f7951a4
_DEFAULT_WELCOME = ("Welcome, {mention}, to {server}!\n\n"
                    "{count} user{plural} joined today!")


class WelcomeCount:
    """Cog which welcomes users to your server and keeps count
    of how many users who have joined that day.

    Idea came from Twentysix's version of Red on the official Red-DiscordBot
    server.
    """

    def __init__(self):
        self.conf = Config.get_conf(
            self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(
            enabled=False, last_message=None, welcome_msg=_DEFAULT_WELCOME)
        self.conf.register_guild(count=0, day=None)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.admin_or_permissions(manage_server=True)
    async def wcount(self, ctx: commands.Context):
        """Manage settings for WelcomeCount."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            channel = ctx.channel
            settings = self.conf.channel(channel)
            if await settings.enabled():
                msg = await settings.welcome_msg()
                await ctx.send(
                    box("Enabled in this channel.\n"
                        "Welcome message: {0}".format(msg)))
            else:
                await ctx.send(box("Disabled in this channel."))

    @wcount.command(name="toggle", pass_context=True)
    async def wcount_toggle(self, ctx: commands.Context):
        """Enable/disable welcome messages in this channel."""
        channel = ctx.channel
        settings = self.conf.channel(channel)
        now_enabled = not await settings.enabled()
        await settings.enabled.set(now_enabled)
        await ctx.send("Welcome messages are now {0} in this channel."
                       "".format("enabled" if now_enabled else "disabled"))

    @wcount.command(name="message", pass_context=True, no_pm=True)
    async def wcount_message(self, ctx: commands.Context, *, message: str):
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
        channel = ctx.channel
        settings = self.conf.channel(channel)
        await settings.welcome_msg.set(message)
        member = ctx.author
        count = await self.conf.guild(ctx.guild).count()
        params = {
            "mention": member.mention,
            "username": member.display_name,
            "server": ctx.guild.name,
            "count": count,
            "plural": "" if count == 1 else "s"
        }
        await ctx.send("Welcome message set, sending a test message here...")
        await ctx.send(message.format(**params))

    # Events

    async def on_member_join(self, member: discord.Member):
        """Send the welcome message and update the last message."""
        guild = member.guild
        server_settings = self.conf.guild(guild)
        today = datetime.date.today()
        new_day = False
        if await server_settings.day() == str(today):
            cur_count = await server_settings.count()
            await server_settings.count.set(cur_count + 1)
        else:
            new_day = True
            await server_settings.day.set(str(today))
            await server_settings.count.set(1)
        welcome_channels = []
        for channel in guild.channels:
            if await self.conf.channel(channel).enabled():
                welcome_channels.append(channel)
        
        last_message = None
        for channel in welcome_channels:
            channel_settings = self.conf.channel(channel)
            if not new_day:
                last_message = await channel_settings.last_message()
                last_message = await channel.get_message(last_message)
                await last_message.delete()
            count = await server_settings.count()
            params = {
                "mention": member.mention,
                "username": member.display_name,
                "server": guild.name,
                "count": count,
                "plural": "" if count == 1 else "s"
            }
            welcome = await channel_settings.welcome_msg()
            msg = await channel.send(welcome.format(**params))
            await channel_settings.last_message.set(msg.id)
