import asyncio
import discord
from discord.ext import commands
from redbot.core import Config, checks

UNIQUE_ID = 0x6AFE8000

class Sticky:
    """Sticky messages."""

    STICKY_DELAY = 3

    def __init__(self, bot):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_channel(stickied=None, last=None)
        self.locked_channels = set()

    async def on_message(self, message: discord.Message):
        """Event which checks for sticky messages to resend."""
        channel = message.channel
        early_exit = (isinstance(channel, discord.abc.PrivateChannel)
                      or channel in self.locked_channels)
        if early_exit:
            return
        settings = self.conf.channel(channel)
        last = await settings.last()
        if last is None or message.id == last:
            return
        try:
            last = await channel.get_message(last)
        except discord.HTTPException:
            pass
        else:
            try:
                await last.delete()
            except discord.NotFound:
                pass

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command()
    async def sticky(self, ctx: commands.Context, *, content: str):
        """Sticky a message to this channel."""
        channel = ctx.channel
        settings = self.conf.channel(channel)
        msg = await self.send_stickied(channel, content)
        chan_data = {
            "stickied": content,
            "last": msg.id
        }
        await settings.set(chan_data)

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command()
    async def unsticky(self, ctx: commands.Context):
        """Remove the sticky message from this channel.

        Deleting the sticky message will also unsticky it.
        """
        channel = ctx.channel
        settings = self.conf.channel(channel)
        self.locked_channels.add(channel)
        last_id = await settings.last()
        if last_id is None:
            await ctx.send("There is no stickied message in this channel.")
            self.locked_channels.remove(channel)
            return
        await ctx.send("This will unsticky the current sticky message from "
                       "this channel. Are you sure you want to do this? (Y/N)")
        _conf_check = lambda m: m.author == ctx.author and m.channel == channel
        try:
            resp = await ctx.bot.wait_for("message", check=_conf_check, timeout=30)
        except asyncio.TimeoutError:
            resp = None
        if resp is None or resp.content.lower() not in ("y", "yes"):
            await ctx.send("Action cancelled.")
            self.locked_channels.remove(channel)
            return
        await settings.clear()
        try:
            last = await channel.get_message(last_id)
        except discord.HTTPException:
            pass
        else:
            try:
                await last.delete()
            except discord.NotFound:
                pass
        await ctx.send("Done.")
        self.locked_channels.remove(channel)

    async def on_raw_message_delete(self, message_id: int, channel_id: int):
        """If the stickied message was deleted, unsticky it."""
        channel = self.bot.get_channel(channel_id)
        settings = self.conf.channel(channel)
        if message_id != await settings.last():
            return
        content = await settings.stickied()
        new = await self.send_stickied(channel, content)
        await settings.last.set(new.id)

    async def send_stickied(self, channel: discord.TextChannel, content: str):
        """Send the content as a stickied message."""
        return await channel.send("__***Stickied Message:***__\n\n" + content)
