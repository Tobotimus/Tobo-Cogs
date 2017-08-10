"""Module for ReactKarma cog."""
import asyncio
from collections import namedtuple
import discord
from discord.ext import commands
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import pagify, box
from . import LOG

UNIQUE_ID = 0x9c02dcc7

class ReactKarma:
    """Keep track of karma for all users in the bot's scope.

    Emojis which affect karma are customised by the owner.
    Upvotes add 1 karma. Downvotes subtract 1 karma."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_user(
            karma=0
        )
        self.conf.register_guild(
            upvote=None,
            downvote=None
        )

    @commands.command()
    @commands.guild_only()
    async def upvote(self, ctx: commands.Context):
        """See this server's upvote emoji."""
        emoji = self._get_emoji(ctx.guild, upvote=True)
        reply = "The upvote emoji in this server is {}".format(emoji)
        if emoji is None:
            reply = ("The upvote emoji in this server is not set."
                     " Use `{0}setupvote` to do so (requires `manage emojis` permission)."
                     "".format(ctx.prefix))
        await ctx.send(reply)

    @commands.command()
    @commands.guild_only()
    async def downvote(self, ctx: commands.Context):
        """See this server's downvote emoji."""
        emoji = self._get_emoji(ctx.guild, upvote=False)
        reply = "The downvote emoji in this server is {}".format(emoji)
        if emoji is None:
            reply = ("The downvote emoji in this server is not set. Admins use"
                     " `{0}setdownvote` to do so (requires `manage emojis` permission)."
                     "".format(ctx.prefix))
        await ctx.send(reply)

    @commands.command()
    async def karmaboard(self, ctx: commands.Context,
                         top: int = 10):
        """Prints out the karma leaderboard

        Defaults to top 10. Use negative numbers to reverse the leaderboard."""
        reverse = True
        if top == 0:
            top = 10
        elif top < 0:
            reverse = False
            top = -top
        members_sorted = sorted(self._get_all_members(),
                                key=lambda x: x.karma, reverse=reverse)
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
    async def get_karma(self, ctx: commands.Context,
                        user: discord.Member=None):
        """Check a user's karma.

        Leave [user] blank to see your own karma."""
        if user is None:
            user = ctx.author
        await ctx.send("{0} has {1} karma."
                       "".format(user.display_name, self.conf.user(user).karma()))

    @commands.command(name="setupvote")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_upvote(self, ctx: commands.Context):
        """Set the upvote emoji in this server by reacting to the bot's response.

        Only the first reaction from the command author will be added."""
        msg = await ctx.send("React to my message with the new upvote emoji!")
        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("Setting the upvote emoji was cancelled.")
            return
        await self._set_reaction(msg.guild, reaction, upvote=True)
        await ctx.send("Done! The upvote emoji in this server is now {}"
                       "".format(self._get_emoji(msg.guild, upvote=True)))

    @commands.command(name="setdownvote")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_downvote(self, ctx: commands.Context):
        """Add a downvote emoji by reacting to the bot's response.

        Only the first reaction from the command author will be added."""
        msg = await ctx.send("React to my message with the new downvote emoji!")
        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("Setting the downvote emoji was cancelled.")
            return
        await self._set_reaction(msg.guild, reaction, upvote=False)
        await ctx.send("Done! The downvote emoji in this server is now {}"
                       "".format(self._get_emoji(msg.guild, upvote=False)))

    @commands.command(name="resetkarma")
    @checks.is_owner()
    async def reset_karma(self, ctx: commands.Context, user: discord.Member):
        """Resets a user's karma."""
        LOG.debug("Resetting %s's karma", str(user))
        await self.conf.user(user).karma.set(0)
        await ctx.send("{}'s karma has been reset to 0.".format(user.display_name))

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being added, and updates karma accordingly.

        Ignores Private Channels and users reacting to their own message."""
        await self._check_reaction(reaction, user, added=True)

    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being removed, and updates karma accordingly.

        Ignores Private Channels and users reacting to their own message."""
        await self._check_reaction(reaction, user, added=False)

    async def _check_reaction(self, reaction: discord.Reaction, user: discord.User, *,
                              added: bool):
        message = reaction.message
        (author, channel, guild) = (message.author, message.channel, message.guild)
        if author == user or isinstance(channel, discord.abc.PrivateChannel):
            return
        emoji = str(reaction.emoji)
        upvote = self._is_upvote(guild, emoji)
        if upvote is not None:
            await self._add_karma(author, 1 if upvote == added else -1)

    async def _add_karma(self, user: discord.User, amount: int):
        settings = self.conf.user(user)
        LOG.debug("%s has been given %d karma.", user, amount)
        await settings.karma.set(settings.karma() + amount)

    async def _set_reaction(self, guild: discord.Guild, reaction: discord.Reaction, *,
                            upvote: bool):
        emoji = str(reaction.emoji)
        settings = self.conf.guild(guild)
        LOG.debug("Setting %s emoji in %s to %s",
                  "upvote" if upvote else "downvote", guild, emoji)
        if upvote:
            await settings.upvote.set(emoji)
        else:
            await settings.downvote.set(emoji)

    def _get_emoji(self, guild: discord.Guild, *, upvote: bool):
        if upvote:
            emoji = self.conf.guild(guild).upvote()
        else:
            emoji = self.conf.guild(guild).downvote()
        return emoji

    def _is_upvote(self, guild: discord.Guild, emoji: str):
        """Returns True if the emoji is the upvote emoji, False
         if it is the downvote emoji, and None otherwise.
        """
        upvote = self._get_emoji(guild, upvote=True)
        downvote = self._get_emoji(guild, upvote=False)
        if emoji == upvote:
            return True
        elif emoji == downvote:
            return False

    def _get_all_members(self):
        """Get a list of members which have karma.

        Returns:
          A list of named tuples with values for `name`, `id`, `karma`"""
        member_info = namedtuple("Member", "id name karma")
        ret = []
        for member in self.bot.get_all_members():
            if self.conf.user(member).karma() != 0 and not any(member.id == m.id for m in ret):
                ret.append(member_info(id=member.id, name=str(member),
                                       karma=self.conf.user(member).karma()))
        return ret
