"""Module for the Sticky cog."""

# Copyright (c) 2017-2018 Tobotimus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import asyncio
import contextlib
import logging

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

UNIQUE_ID = 0x6AFE8000

log = logging.getLogger("red.sticky")


class Sticky(commands.Cog):
    """Sticky messages to your channels."""

    STICKY_DELAY = 3

    def __init__(self, bot):
        super().__init__()

        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(stickied=None, last=None)
        self.locked_channels = set()

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command()
    async def sticky(self, ctx: commands.Context, *, content: str):
        """Sticky a message to this channel."""
        channel = ctx.channel
        settings = self.conf.channel(channel)
        msg = await self.send_stickied(channel, content)
        chan_data = {"stickied": content, "last": msg.id}
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
        try:
            last_id = await settings.last()
            if last_id is None:
                await ctx.send("There is no stickied message in this channel.")
                return
            msg = await ctx.send(
                "This will unsticky the current sticky message from "
                "this channel. Are you sure you want to do this?"
            )
            start_adding_reactions(
                msg, emojis=ReactionPredicate.YES_OR_NO_EMOJIS, loop=ctx.bot.loop
            )

            pred = ReactionPredicate.yes_or_no(msg)
            try:
                resp = await ctx.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                resp = None
            if resp is None or pred.result is False:
                await ctx.send("Action cancelled.")
                with contextlib.suppress(discord.Forbidden):
                    await msg.clear_reactions()
                return
            await settings.clear()
            try:
                last = await channel.fetch_message(last_id)
            except discord.HTTPException:
                pass
            else:
                try:
                    await last.delete()
                except discord.NotFound:
                    pass
            await ctx.send("Done.")
        finally:
            self.locked_channels.remove(channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Event which checks for sticky messages to resend."""
        channel = message.channel
        early_exit = (
            isinstance(channel, discord.abc.PrivateChannel)
            or channel in self.locked_channels
        )
        if early_exit:
            return
        settings = self.conf.channel(channel)
        last = await settings.last()
        if last is None or message.id == last:
            return
        try:
            last = await channel.fetch_message(last)
        except discord.NotFound:
            pass
        except discord.Forbidden:
            log.fatal(
                "The bot does not have permission to retreive the stickied message"
            )
        else:
            with contextlib.suppress(discord.NotFound):
                await last.delete()

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.raw_models.RawMessageDeleteEvent
    ):
        """If the stickied message was deleted, re-post it."""
        channel = self.bot.get_channel(payload.channel_id)
        settings = self.conf.channel(channel)
        if payload.message_id != await settings.last():
            return
        content = await settings.stickied()
        new = await self.send_stickied(channel, content)
        await settings.last.set(new.id)

    @staticmethod
    async def send_stickied(channel: discord.TextChannel, content: str):
        """Send the content as a stickied message."""
        return await channel.send("__***Stickied Message:***__\n\n" + content)
