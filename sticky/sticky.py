"""Module for the Sticky cog."""
import asyncio
import contextlib
import logging
from typing import Any, Dict, Optional, Union

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
        self.conf.register_channel(
            stickied=None,  # This is for [p]sticky
            header_enabled=True,
            advstickied={"content": None, "embed": {}},  # This is for [p]stickyexisting
            last=None,
        )
        self.locked_channels = set()

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group(invoke_without_command=True)
    async def sticky(self, ctx: commands.Context, *, content: str):
        """Sticky a message to this channel."""
        channel = ctx.channel
        settings = self.conf.channel(channel)
        header_enabled = await settings.header_enabled()
        to_send = (
            f"__***Stickied Message***__\n\n{content}" if header_enabled else content
        )
        msg = await channel.send(to_send)

        await settings.set(
            {"stickied": content, "header_enabled": header_enabled, "last": msg.id}
        )

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
        stickied_msg = await self.send_advstickied(
            channel, content, embed, header_enabled=await settings.header_enabled()
        )
        embed_data = embed.to_dict() if embed is not None else None
        await settings.set(
            {
                "advstickied": {"content": content, "embed": embed_data},
                "last": stickied_msg.id,
                # We don't want to overwrite the header setting
                "header_enabled": await settings.header_enabled(),
            }
        )

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
        self.locked_channels.add(channel)
        try:
            last_id = await settings.last()
            if last_id is None:
                await ctx.send("There is no stickied message in this channel.")
                return
            msg = None
            if not force and channel.permissions_for(ctx.me).add_reactions:
                msg = await ctx.send(
                    "This will unsticky the current sticky message from "
                    "this channel. Are you sure you want to do this?"
                )
                start_adding_reactions(msg, emojis=ReactionPredicate.YES_OR_NO_EMOJIS)

                pred = ReactionPredicate.yes_or_no(msg)
                try:
                    resp = await ctx.bot.wait_for(
                        "reaction_add", check=pred, timeout=30
                    )
                except asyncio.TimeoutError:
                    resp = None
                if resp is None or pred.result is False:
                    with contextlib.suppress(discord.NotFound):
                        await msg.delete()
                    return
            else:
                await ctx.send(
                    f"I don't have the add_reactions permission here. "
                    f"Use `{ctx.prefix}unsticky yes` to remove the sticky message."
                )
                return

            await settings.set(
                # Preserve the header setting
                {"header_enabled": await settings.header_enabled()}
            )
            with contextlib.suppress(discord.HTTPException):
                last = await channel.fetch_message(last_id)
                await last.delete()

            if msg is not None:
                with contextlib.suppress(discord.NotFound):
                    await msg.delete()
            await ctx.tick()
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
        settings_dict = await settings.all()
        if payload.message_id != settings_dict["last"]:
            return
        header = settings_dict["header_enabled"]
        if settings_dict["stickied"] is not None:
            content = settings_dict["stickied"]
            to_send = f"__***Stickied Message***__\n\n{content}" if header else content
            new = await channel.send(to_send)
        else:
            advstickied = settings_dict["advstickied"]
            if advstickied["content"] or advstickied["embed"]:
                new = await self.send_advstickied(
                    channel, **advstickied, header_enabled=header
                )
            else:
                # The last stickied message was deleted but there's nothing to send
                await settings.last.clear()
                return

        await settings.last.set(new.id)

    @staticmethod
    async def send_advstickied(
        channel: discord.TextChannel,
        content: Optional[str],
        embed: Optional[Union[discord.Embed, Dict[str, Any]]],
        *,
        header_enabled: bool = False,
    ):
        """Send the content and embed as a stickied message."""
        if embed and isinstance(embed, dict):
            embed = discord.Embed.from_dict(embed)
        if header_enabled:
            header_text = "__***Stickied Message***__"
            content = f"{header_text}\n\n{content}" if content else header_text
        return await channel.send(content, embed=embed)
