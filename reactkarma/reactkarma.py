import os
import discord
from collections import namedtuple
from discord.ext import commands
from discord.ext.commands.bot import Bot
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import inline, pagify, box
from unicodedata import name, lookup

FOLDER_PATH = "data/reactkarma"
KARMA_PATH = "{}/karma.json".format(FOLDER_PATH)
SETTINGS_PATH = "{}/settings.json".format(FOLDER_PATH)
DOWNVOTE = "downvote"
UPVOTE = "upvote"

class ReactKarma():
    """Keep track of karma for all users in the bot's scope. 
    
    Emojis which affect karma are customised by the owner.
    Upvotes add 1 karma. Downvotes subtract 1 karma."""

    def __init__(self, bot):
        self.bot = bot
        self.karma = dataIO.load_json(KARMA_PATH)
        self.settings = dataIO.load_json(SETTINGS_PATH)
        self.setting_emojis = False # For knowing when emojis are being added/removed

    @commands.command(pass_context=True, no_pm=True)
    async def upvote(self, ctx):
        """See this server's upvote emoji."""
        emoji = self._get_emoji(ctx.message.server, UPVOTE)
        msg = "The upvote emoji in this server is {}".format(emoji)
        if emoji is None:
            msg = "The upvote emoji in this server is not set. Use !setupvote to do so (requires `manage emojis` permission)."
        await self.bot.say(msg)

    @commands.command(pass_context=True, no_pm=True)
    async def downvote(self, ctx):
        """See this server's downvote emoji."""
        emoji = self._get_emoji(ctx.message.server, DOWNVOTE)
        msg = "The downvote emoji in this server is {}".format(emoji)
        if emoji is None:
            msg = "The downvote emoji in this server is not set. Admins use !setdownvote to do so (requires `manage emojis` permission)."
        await self.bot.say(msg)

    @commands.command()
    async def karmaboard(self, top: int=10):
        """Prints out the karma leaderboard

        Defaults to top 10. Use negative numbers to reverse the leaderboard."""
        reverse=True
        if top == 0:
            top = 10
        elif top < 0:
            reverse=False
            top = -top
        self.karma = dataIO.load_json(KARMA_PATH)
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
                await self.bot.say(box(page, lang="py"))
        else:
            await self.bot.say("No one has any karma 🙁")

    @commands.command(name="karma", pass_context=True)
    async def get_karma(self, ctx, user: discord.Member=None):
        """Check a user's karma. 

        Leave [user] blank to see your own karma."""
        if user is None: 
            user = ctx.message.author
        self.karma = dataIO.load_json(KARMA_PATH)
        if user.id in self.karma:
            _karma = self.karma[user.id]
            await self.bot.say("{} has {} karma.".format(user.display_name, _karma))
        else:
            await self.bot.say("{} has never received any karma!".format(user.display_name))
            return

    @commands.command(name="setupvote", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_upvote(self, ctx):
        """Set the upvote emoji in this server by reacting to the bot's response.
        
        Only reactions from the command author will be added."""
        msg = await self.bot.say("React to my message with the new upvote emoji!")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        if response is not None:
           self._set_reaction(msg.server, response.reaction, UPVOTE)
        self.setting_emojis = False
        msg = "Done! The upvote emoji in this server is now {}".format(self._get_emoji(msg.server, UPVOTE))
        if response is None:
            msg = "Setting the upvote emoji was cancelled."
        await self.bot.say(msg)
        
    @commands.command(name="setdownvote", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_emojis=True)
    async def set_downvote(self, ctx):
        """Add a downvote emoji by reacting to the bot's response.
        
        Only reactions from the command author will be added."""
        msg = await self.bot.say("React to my message with the new downvote emoji!")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        if response is not None:
           self._set_reaction(msg.server, response.reaction, DOWNVOTE)
        self.setting_emojis = False
        msg = "Done! The downvote emoji in this server is now {}".format(self._get_emoji(msg.server, DOWNVOTE))
        if response is None:
            msg = "Setting the downvote emoji was cancelled."
        await self.bot.say(msg)

    @commands.command(name="resetkarma", pass_context=True)
    @checks.is_owner()
    async def reset_karma(self, ctx, user: discord.Member=None):
        """"Resets a user's karma. 
        
        Resets karma of all users if user is left blank"""
        if user is None:
            await self.bot.say("This will remove all karma from all members across all servers. "
                               "Are you sure you want to do this? Type `yes` to continue.")
            accepted = await self.bot.wait_for_message(author=ctx.message.author, content="yes", timeout=15.0)
            if accepted is not None:
                self.karma = {}
                dataIO.save_json(KARMA_PATH, self.karma)
                await self.bot.say("Karma reset.")
            else:
                await self.bot.say("Reset cancelled.")
        else:
            try:
                self.karma[user.id] = 0
                dataIO.save_json(KARMA_PATH, self.karma)
                await self.bot.say("{}'s karma has been reset.".format(user.display_name))
            except KeyError:
                await self.bot.say("{} has never received any karma!".format(user.display_name))

    async def _reaction_added(self, reaction: discord.Reaction, user: discord.User):
        if self.setting_emojis: return # Don't change karma whilst adding/removing emojis
        server = reaction.message.server
        author = reaction.message.author
        if author == user: return # Users can't change their own karma
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        try:
            if emoji == self.settings[server.id][UPVOTE]:
                self._add_karma(author.id, 1)
            elif emoji == self.settings[server.id][DOWNVOTE]:
                self._add_karma(author.id, -1)
        except:
            return

    async def _reaction_removed(self, reaction: discord.Reaction, user: discord.User):
        if self.setting_emojis: return # Don't change karma whilst adding/removing emojis
        server = reaction.message.server
        author = reaction.message.author
        if author == user: return # Users can't change their own karma
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        try:
            if emoji == self.settings[server.id][UPVOTE]:
                self._add_karma(author.id, -1)
            elif emoji == self.settings[server.id][DOWNVOTE]:
                self._add_karma(author.id, 1)
        except:
            return

    def _set_reaction(self, server, reaction: discord.Reaction, type):
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        if server.id not in self.settings: 
            self.settings[server.id] = {}
        self.settings[server.id][type] = emoji
        dataIO.save_json(SETTINGS_PATH, self.settings)

    def _get_emoji(self, server, type):
        if server.id not in self.settings:
            return None
        if type in self.settings[server.id]:
            emoji_name = self.settings[server.id][type]
            emoji = discord.utils.get(server.emojis, name=emoji_name)
            if emoji is None:
                try:
                    emoji = lookup(emoji_name)
                except:
                    return None
            return emoji

    def _add_karma(self, user_id, amount: int):
        self.karma = dataIO.load_json(KARMA_PATH)
        if user_id not in self.karma:
            self.karma[user_id] = 0
        self.karma[user_id] += amount
        dataIO.save_json(KARMA_PATH, self.karma)

    def _get_all_members(self):
        """Get a list of members which have karma.
        
        Returns:
          A list of named tuples with values for `name`, `id`, `karma`"""
        members = []
        KarmaMember = namedtuple("Member", "id name karma")
        for user_id, karma in self.karma.items():
            member = discord.utils.get(self.bot.get_all_members(), id=user_id)
            if member is None: continue
            member = KarmaMember(id=member.id, name=str(member), karma=karma)
            members.append(member)
        return members

def check_folders():
    if not os.path.exists(FOLDER_PATH):
        print("Creating {} folder...".format(FOLDER_PATH))
        os.makedirs(FOLDER_PATH)

def check_files():
    if not dataIO.is_valid_json(KARMA_PATH):
        dataIO.save_json(KARMA_PATH, {})
    if not dataIO.is_valid_json(SETTINGS_PATH):
        dataIO.save_json(SETTINGS_PATH, {})

def setup(bot):
    check_folders()
    check_files()
    n = ReactKarma(bot)
    bot.add_listener(n._reaction_added, "on_reaction_add")
    bot.add_listener(n._reaction_removed, "on_reaction_remove")
    bot.add_cog(n)