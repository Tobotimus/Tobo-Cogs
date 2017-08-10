"""Module for ReactKarma cog."""
from collections import namedtuple
from unicodedata import name, lookup
import discord
from discord.ext import commands
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import pagify, box

UNIQUE_ID = 0x9c02dcc7
_DOWNVOTE = "downvote"
_UPVOTE = "upvote"

class ReactKarma:
    """Keep track of karma for all users in the bot's scope.

    Emojis which affect karma are customised by the owner.
    Upvotes add 1 karma. Downvotes subtract 1 karma."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_user(
            karma=0
        )
        self.conf.register_guild(
            upvote=None,
            downvote=None
        )
        self.setting_emojis = False # For knowing when emojis are being added/removed

    @commands.command(no_pm=True)
    async def upvote(self, ctx: commands.Context):
        """See this server's upvote emoji."""
        emoji = self._get_emoji(ctx.guild, _UPVOTE)
        reply = "The upvote emoji in this server is {}".format(emoji)
        if emoji is None:
            reply = ("The upvote emoji in this server is not set."
                     " Use !setupvote to do so (requires `manage emojis` permission).")
        await ctx.send(reply)

    @commands.command(no_pm=True)
    async def downvote(self, ctx: commands.Context):
        """See this server's downvote emoji."""
        emoji = self._get_emoji(ctx.guild, _DOWNVOTE)
        reply = "The downvote emoji in this server is {}".format(emoji)
        if emoji is None:
            reply = ("The downvote emoji in this server is not set. Admins use"
                     " !setdownvote to do so (requires `manage emojis` permission).")
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
            highscore += ("{} | ".format(member.name)
                         ).ljust(18 - len(str(member.karma)))
            highscore += str(member.karma) + "\n"
            place += 1
        if highscore != "":
            for page in pagify(highscore, shorten_by=12):
                await ctx.send(box(page, lang="py"))
        else:
            await ctx.send("No one has any karma 🙁")

    @commands.command(name="karma")
    async def get_karma(self, ctx: commands.Context,
                        user: discord.Member=None):
        """Check a user's karma.

        Leave [user] blank to see your own karma."""
        if user is None:
            user = ctx.author
        if user.id in self.conf.karma():
            _karma = self.conf.karma()[user.id]
            await ctx.send("{0} has {1} karma.".format(user.display_name, _karma))
        else:
            await ctx.send("{0} has never received any karma!".format(user.display_name))
            return

    @commands.command(name="setupvote", no_pm=True)
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_upvote(self, ctx: commands.Context):
        """Set the upvote emoji in this server by reacting to the bot's response.

        Only reactions from the command author will be added."""
        msg = await ctx.send("React to my message with the new upvote emoji!")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(
            user=ctx.author, message=msg, timeout=10.0)
        if response is not None:
            self._set_reaction(msg.guild, response.reaction, _UPVOTE)
        self.setting_emojis = False
        reply = ("Done! The upvote emoji in this server is now {}"
                 "".format(self._get_emoji(msg.guild, _UPVOTE)))
        if response is None:
            reply = "Setting the upvote emoji was cancelled."
        await ctx.send(reply)

    @commands.command(name="setdownvote", no_pm=True)
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_downvote(self, ctx: commands.Context):
        """Add a downvote emoji by reacting to the bot's response.

        Only reactions from the command author will be added."""
        msg = await ctx.send("React to my message with the new downvote emoji!")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(
            user=ctx.author, message=msg, timeout=10.0)
        if response is not None:
            self._set_reaction(msg.guild, response.reaction, _DOWNVOTE)
        self.setting_emojis = False
        reply = ("Done! The downvote emoji in this server is now {}"
                 "".format(self._get_emoji(msg.guild, _DOWNVOTE)))
        if response is None:
            reply = "Setting the downvote emoji was cancelled."
        await ctx.send(reply)

    @commands.command(name="resetkarma")
    @checks.is_owner()
    async def reset_karma(self, ctx: commands.Context,
                          user: discord.Member=None):
        """"Resets a user's karma.

        Resets karma of all users if user is left blank"""
        if user is None:
            await ctx.send("This will remove all karma from all members across all servers. "
                           "Are you sure you want to do this? Type `yes` to continue.")
            response = await self.bot.wait_for_message(
                author=ctx.author, content="yes", timeout=15.0)
            if response is not None:
                self.conf.set('karma', {})
                await ctx.send("Karma reset.")
            else:
                await ctx.send("Reset cancelled.")
        else:
            try:
                _karma = self.conf.karma()
                _karma[user.id] = 0
                self.conf.set('karma', _karma)
                await ctx.send("{}'s karma has been reset.".format(user.display_name))
            except KeyError:
                await ctx.send("{} has never received any karma!".format(user.display_name))

    async def reaction_added(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being added."""
        if self.setting_emojis:
            return # Don't change karma whilst adding/removing emojis
        guild = reaction.message.guild
        author = reaction.message.author
        if author == user:
            return # Users can't change their own karma
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        if emoji == self._get_emoji(guild, _UPVOTE):
            self._add_karma(author.id, -1)
        elif emoji == self._get_emoji(guild, _DOWNVOTE):
            self._add_karma(author.id, 1)

    async def reaction_removed(self, reaction: discord.Reaction, user: discord.User):
        """Fires when the bot sees a reaction being removed."""
        if self.setting_emojis:
            return # Don't change karma whilst adding/removing emojis
        guild = reaction.message.guild
        author = reaction.message.author
        if author == user:
            return # Users can't change their own karma
        emoji = reaction.emoji
        if emoji == self._get_emoji(guild, _UPVOTE):
            self._add_karma(author.id, -1)
        elif emoji == self._get_emoji(guild, _DOWNVOTE):
            self._add_karma(author.id, 1)

    def _set_reaction(self, guild: discord.Guild, reaction: discord.Reaction, reaction_type):
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        self.conf.guild(guild).set(reaction_type, emoji)

    def _get_emoji(self, guild: discord.Guild, reaction_type):
        if reaction_type == _UPVOTE:
            emoji_name = self.conf.guild(guild).upvote()
        elif reaction_type == _DOWNVOTE:
            emoji_name = self.conf.guild(guild).downvote()
        if emoji_name is None:
            return
        emoji = discord.utils.get(guild.emojis, name=emoji_name)
        if emoji is None:
            try:
                emoji = lookup(emoji_name)
            except KeyError:
                return None
        return emoji

    def _add_karma(self, user: discord.User, amount: int):
        _karma = self.conf.user(user).karma()
        _karma += amount
        self.conf.user(user).set('karma', _karma)

    def _get_all_members(self):
        """Get a list of members which have karma.

        Returns:
          A list of named tuples with values for `name`, `id`, `karma`"""
        members = []
        member_info = namedtuple("Member", "id name karma")
        for member in self.bot.get_all_members():
            if self.conf.user(member).karma() != 0:
                member = member_info(id=member.id, name=str(member),
                                     karma=self.conf.user(member).karma())
                members.append(member)
        return members
