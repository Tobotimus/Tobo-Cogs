"""Module for the Sticky cog."""
import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

UNIQUE_ID = 0x6AFE8000

log = logging.getLogger("red.sticky")


class Sticky(commands.Cog):
    """Sticky messages to your channels."""

    REPOST_COOLDOWN = 3

    def __init__(self, bot):
        super().__init__()

        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(
            stickied=None,  # This is for [p]sticky
            header_enabled=True,
            advstickied={"content": None, "embed": {}},  # This is for [p]stickyexisting
            last=None,
        )
        self.locked_channels = set()
        self._channel_cvs: Dict[discord.TextChannel, asyncio.Condition] = {}

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group(invoke_without_command=True)
    async def sticky(self, ctx: commands.Context, *, content: str):
        """Sticky a message to this channel."""
        channel = ctx.channel
        settings = self.conf.channel(channel)

        async with settings.all() as settings_dict:
            settings_dict = cast(Dict[str, Any], settings_dict)

            settings_dict.pop("advstickied", None)
            settings_dict["stickied"] = content

            msg = await self._send_stickied_message(channel, settings_dict)

            if settings_dict["last"] is not None:
                last_message = channel.get_partial_message(settings_dict["last"])
                with contextlib.suppress(discord.NotFound):
                    await last_message.delete()

            settings_dict["last"] = msg.id

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @sticky.command(name="existing")
    async def sticky_existing(
        self, ctx: commands.Context, *, message_id_or_url: discord.Message
    ):
        """Sticky an existing message to this channel.

        This will try to sticky the content and embed of the message.
        Attachments will not be added to the stickied message.

        Stickying messages with multiple embeds may result in unexpected
        behaviour, as the bot cannot send multiple rich embeds in a
        single message.
        """
        message = message_id_or_url
        del message_id_or_url
        channel = ctx.channel
        settings = self.conf.channel(channel)
        if not (message.content or message.embeds):
            await ctx.send("That message doesn't have any content or embed!")
            return
        embed = next(iter(message.embeds), None)
        content = message.content or None
        embed_data = embed.to_dict() if embed is not None else None

        async with settings.all() as settings_dict:
            settings_dict = cast(Dict[str, Any], settings_dict)

            settings_dict.pop("stickied", None)
            settings_dict["advstickied"] = {"content": content, "embed": embed_data}

            msg = await self._send_stickied_message(channel, settings_dict)

            if settings_dict["last"] is not None:
                last_message = channel.get_partial_message(settings_dict["last"])
                with contextlib.suppress(discord.NotFound):
                    await last_message.delete()

            settings_dict["last"] = msg.id

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @sticky.command(name="toggleheader")
    async def sticky_toggleheader(self, ctx: commands.Context, true_or_false: bool):
        """Toggle the header for stickied messages in this channel.

        The header is enabled by default.
        """
        await self.conf.channel(ctx.channel).header_enabled.set(true_or_false)
        await ctx.tick()

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command()
    async def unsticky(self, ctx: commands.Context, force: bool = False):
        """Remove the sticky message from this channel.

        Deleting the sticky message will also unsticky it.

        Do `[p]unsticky yes` to skip the confirmation prompt.
        """
        channel = ctx.channel
        settings = self.conf.channel(channel)
        async with self._lock_channel(channel):
            last_id = await settings.last()
            if last_id is None:
                await ctx.send("There is no stickied message in this channel.")
                return

            if not (force or await self._confirm_unsticky(ctx)):
                return

            await settings.set(
                # Preserve the header setting
                {"header_enabled": await settings.header_enabled()}
            )
            last = channel.get_partial_message(last_id)
            with contextlib.suppress(discord.HTTPException):
                await last.delete()

            await ctx.tick()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Event which checks for sticky messages to resend."""
        channel = message.channel
        if isinstance(channel, discord.abc.PrivateChannel):
            return

        await self._maybe_repost_stickied_message(
            channel,
            responding_to_message=message,
            delete_last=True,
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.raw_models.RawMessageDeleteEvent
    ):
        """If the stickied message was deleted, re-post it."""
        channel = self.bot.get_channel(payload.channel_id)
        settings = self.conf.channel(channel)
        if payload.message_id != await settings.last():
            return

        await self._maybe_repost_stickied_message(channel)

    async def _maybe_repost_stickied_message(
        self,
        channel: discord.TextChannel,
        responding_to_message: Optional[discord.Message] = None,
        *,
        delete_last: bool = False,
    ) -> None:
        cv = self._channel_cvs.setdefault(channel, asyncio.Condition())
        settings = self.conf.channel(channel)

        async with cv:
            await cv.wait_for(lambda: channel not in self.locked_channels)

            settings_dict = await settings.all()
            last_message_id = settings_dict["last"]
            if last_message_id is None:
                return

            last_message = channel.get_partial_message(last_message_id)
            if responding_to_message and (
                # We don't want to respond to our own message, and we
                # don't want to respond to a message older than our last
                # message.
                responding_to_message.id == last_message_id
                or responding_to_message.created_at < last_message.created_at
            ):
                return

            # Discord.py 2.0 uses timezone-aware timestamps, so we need
            # to do the same to compare the timestamps.
            if last_message.created_at.tzinfo is None:
                utcnow = datetime.utcnow()
            else:
                utcnow = datetime.now(timezone.utc)

            time_since = utcnow - last_message.created_at
            time_to_wait = self.REPOST_COOLDOWN - time_since.total_seconds()
            if time_to_wait > 0:
                await asyncio.sleep(time_to_wait)

            if not (
                settings_dict["stickied"] or any(settings_dict["advstickied"].values())
            ):
                # There's nothing to send
                await settings.last.clear()
                return

            new = await self._send_stickied_message(channel, settings_dict)

            await settings.last.set(new.id)

            if delete_last:
                with contextlib.suppress(discord.NotFound):
                    await last_message.delete()

    @staticmethod
    async def _send_stickied_message(
        channel: discord.TextChannel, settings_dict: Dict[str, Any]
    ):
        """Send the content and/or embed as a stickied message."""
        embed = None
        header_enabled = settings_dict["header_enabled"]
        header_text = "__***Stickied Message***__"
        if settings_dict.get("stickied") is not None:
            content = settings_dict["stickied"]
            if header_enabled:
                content = f"{header_text}\n\n{content}"
        else:
            content = settings_dict["advstickied"]["content"]
            embed_dict = settings_dict["advstickied"]["embed"]
            if embed_dict:
                embed = discord.Embed.from_dict(embed_dict)
            if header_enabled:
                content = f"{header_text}\n\n{content}" if content else header_text

        return await channel.send(content, embed=embed)

    @contextlib.asynccontextmanager
    async def _lock_channel(self, channel: discord.TextChannel) -> None:
        cv = self._channel_cvs.setdefault(channel, asyncio.Condition())
        async with cv:
            self.locked_channels.add(channel)
            try:
                yield
            finally:
                with contextlib.suppress(KeyError):
                    self.locked_channels.remove(channel)
                    cv.notify_all()

    @staticmethod
    async def _confirm_unsticky(ctx: commands.Context) -> bool:
        msg_content = (
            "This will unsticky the current sticky message from "
            "this channel. Are you sure you want to do this?"
        )
        if not ctx.channel.permissions_for(ctx.me).add_reactions:
            event = "message"
            msg = await ctx.send(f"{msg_content} (y/n)")
            predicate = MessagePredicate.yes_or_no(ctx)
        else:
            event = "reaction_add"
            msg = await ctx.send(
                "This will unsticky the current sticky message from "
                "this channel. Are you sure you want to do this?"
            )
            predicate = ReactionPredicate.yes_or_no(msg, ctx.author)
            start_adding_reactions(msg, emojis=ReactionPredicate.YES_OR_NO_EMOJIS)

        try:
            resp = await ctx.bot.wait_for(event, check=predicate, timeout=30)
        except asyncio.TimeoutError:
            resp = None
        if resp is None or not predicate.result:
            with contextlib.suppress(discord.NotFound):
                await msg.delete()

        return predicate.result
