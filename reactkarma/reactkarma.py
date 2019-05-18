"""Module for the ReactKarma cog."""

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
import logging
from collections import namedtuple

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, pagify

log = logging.getLogger("red.reactkarma")

__all__ = ["UNIQUE_ID", "ReactKarma"]

UNIQUE_ID = 0x9C02DCC7


class ReactKarma(getattr(commands, "Cog", object)):
    """Keep track of karma for all users in the bot's scope.

    Emojis which affect karma are customised by the owner.
    Upvotes add 1 karma. Downvotes subtract 1 karma.
    """

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_user(karma=0)
        self.conf.register_guild(upvote=None, downvote=None)

    @commands.command()
    @commands.guild_only()
    async def upvote(self, ctx: commands.Context):
        """See this server's upvote emoji."""
        emoji = await self.conf.guild(ctx.guild).upvote()
        if isinstance(emoji, int):
            emoji = ctx.bot.get_emoji(emoji)
        if emoji is None:
            reply = (
                "The upvote emoji in this server is not set."
                " Use `{0}setupvote` to do so (requires `manage emojis`"
                " permission).".format(ctx.prefix)
            )
        else:
            reply = "The upvote emoji in this server is {!s}".format(emoji)
        await ctx.send(reply)

    @commands.command()
    @commands.guild_only()
    async def downvote(self, ctx: commands.Context):
        """See this server's downvote emoji."""
        emoji = await self.conf.guild(ctx.guild).downvote()
        if isinstance(emoji, int):
            emoji = ctx.bot.get_emoji(emoji)
        if emoji is None:
            reply = (
                "The downvote emoji in this server is not set. Admins use"
                " `{0}setdownvote` to do so (requires `manage emojis`"
                " permission).".format(ctx.prefix)
            )
        else:
            reply = "The downvote emoji in this server is {!s}".format(emoji)
        await ctx.send(reply)

    @commands.command()
    async def karmaboard(self, ctx: commands.Context, top: int = 10):
        """Prints out the karma leaderboard.

        Defaults to top 10. Use negative numbers to reverse the leaderboard.
        """
        reverse = True
        if top == 0:
            top = 10
        elif top < 0:
            reverse = False
            top = -top
        members_sorted = sorted(
            await self._get_all_members(ctx.bot), key=lambda x: x.karma, reverse=reverse
        )
        if len(members_sorted) < top:
            top = len(members_sorted)
        topten = members_sorted[:top]
        highscore = ""
        place = 1
        for member in topten:
            highscore += str(place).ljust(len(str(top)) + 1)
            highscore += "{} | ".format(member.name).ljust(18 - len(str(member.karma)))
            highscore += str(member.karma) + "\n"
            place += 1
        if highscore != "":
            for page in pagify(highscore, shorten_by=12):
                await ctx.send(box(page, lang="py"))
        else:
            await ctx.send("No one has any karma 🙁")

    @commands.command(name="karma")
    @commands.guild_only()
    async def get_karma(self, ctx: commands.Context, user: discord.Member = None):
        """Check a user's karma.

        Leave [user] blank to see your own karma.
        """
        if user is None:
            user = ctx.author
        karma = await self.conf.user(user).karma()
        await ctx.send("{0} has {1} karma." "".format(user.display_name, karma))

    @commands.command(name="setupvote")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_upvote(self, ctx: commands.Context):
        """Set the upvote emoji in this server.

        Only the first reaction from the command author will be added.
        """
        await self._interactive_emoji_setup(ctx, "upvote")

    @commands.command(name="setdownvote")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_downvote(self, ctx: commands.Context):
        """Add a downvote emoji by reacting to the bot's response.

        Only the first reaction from the command author will be added.
        """
        await self._interactive_emoji_setup(ctx, "downvote")

    async def _interactive_emoji_setup(self, ctx: commands.Context, type_: str):
        msg = await ctx.send(
            "React to my message with the new {} emoji!" "".format(type_)
        )
        try:
            reaction, _ = await ctx.bot.wait_for(
                "reaction_add",
                check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            await ctx.send("Setting the {} emoji was cancelled.".format(type_))
            return
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            save = emoji.id
        elif isinstance(emoji, discord.PartialEmoji):
            await ctx.send(
                "Setting the {} failed. This is a custom emoji"
                " which I cannot see.".format(type_)
            )
            return
        else:
            save = emoji
        value = getattr(self.conf.guild(ctx.guild), type_)
        await value.set(save)
        await ctx.send(
            "Done! The {} emoji in this server is now {!s}" "".format(type_, emoji)
        )

    @commands.command(name="resetkarma")
    @checks.is_owner()
    async def reset_karma(self, ctx: commands.Context, user: discord.Member):
        """Resets a user's karma."""
        log.debug("Resetting %s's karma", str(user))
        # noinspection PyTypeChecker
        await self.conf.user(user).karma.set(0)
        await ctx.send("{}'s karma has been reset to 0.".format(user.display_name))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being added, and updates karma.

        Ignores Private Channels and users reacting to their own message.
        """
        await self._check_reaction(reaction, user, added=True)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being removed, and updates karma.

        Ignores Private Channels and users reacting to their own message.
        """
        await self._check_reaction(reaction, user, added=False)

    async def _check_reaction(
        self, reaction: discord.Reaction, user: discord.User, *, added: bool
    ):
        message = reaction.message
        (author, channel, guild) = (message.author, message.channel, message.guild)
        if author == user or isinstance(channel, discord.abc.PrivateChannel):
            return
        emoji = reaction.emoji
        upvote = await self._is_upvote(guild, emoji)
        if upvote is not None:
            await self._add_karma(author, 1 if upvote == added else -1)

    async def _add_karma(self, user: discord.User, amount: int):
        settings = self.conf.user(user)
        karma = await settings.karma()
        await settings.karma.set(karma + amount)

    async def _get_emoji_id(self, guild: discord.Guild, *, upvote: bool):
        if upvote:
            emoji = await self.conf.guild(guild).upvote()
        else:
            emoji = await self.conf.guild(guild).downvote()
        return emoji

    async def _is_upvote(self, guild: discord.Guild, emoji):
        """Check if the given emoji is an upvote.

        Returns True if the emoji is the upvote emoji, False f it is the
        downvote emoji, and None otherwise.
        """
        upvote = await self.conf.guild(guild).upvote()
        downvote = await self.conf.guild(guild).downvote()
        if isinstance(upvote, int) and isinstance(emoji, discord.Emoji):
            if emoji.id == upvote:
                return True
            if emoji == downvote:
                return False
        if emoji == upvote:
            return True
        elif emoji == downvote:
            return False

    async def _get_all_members(self, bot):
        """Get a list of members which have karma.

        Returns a list of named tuples with values for `name`, `id`, `karma`.
        """
        member_info = namedtuple("Member", "id name karma")
        ret = []
        for member in bot.get_all_members():
            if any(member.id == m.id for m in ret):
                continue
            karma = await self.conf.user(member).karma()
            if karma == 0:
                continue
            ret.append(member_info(id=member.id, name=str(member), karma=karma))
        return ret
