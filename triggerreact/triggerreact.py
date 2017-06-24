"""Module for the TriggerReact cog."""
import os
import logging
from unicodedata import name, lookup
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import pagify

_LOGGER = logging.getLogger("red.triggerreact")
FOLDER_PATH = "data/triggerreact"
TRIGGERS_PATH = FOLDER_PATH + "/triggers.json"
DEFAULT_SETTINGS = {
    "text_triggers": {},
    "user_triggers": {}
}

class TriggerReact:
    """React to messages based on user-defined triggers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.triggers = _load()

    async def trigger_reactions(self, message):
        """Fires when the bot sees a message being sent, and
         triggers any reactions.
        """
        def _triggered_reactions():
            for text, emoji in self.triggers['text_triggers'].items():
                if text in message.content.lower():
                    yield self._lookup_emoji(emoji)
            for user_id, emoji in self.triggers['user_triggers'].items():
                if user_id == message.author.id:
                    yield self._lookup_emoji(emoji)
        for emoji in _triggered_reactions():
            try:
                await self.bot.add_reaction(message, emoji)
            except (discord.errors.ClientException, discord.errors.HTTPException):
                pass

    @commands.group(name="triggerreact", aliases=["treact"], pass_context=True)
    @checks.is_owner()
    async def trigger_set(self, ctx: commands.Context):
        """Manage the triggers for reactions. These are global, unless the reaction
         is a server emoji.

        To delete a trigger, reset the trigger with no reaction.
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @trigger_set.command(name="text", pass_context=True)
    async def trigger_set_text(self, ctx: commands.Context, *,
                               text: str):
        """Trigger if a message contains a word or phrase.

        This text is not case sensitive and strips the message of leading
         or trailing whitespace.
        """
        text = text.strip().lower()
        emoji = await self._get_trigger_emoji(ctx.message.author)
        if emoji:
            self.triggers["text_triggers"][text] = emoji
            _save(self.triggers)
            await self.bot.say("Done - I will now react to messages containing `{text}` with"
                               " {emoji}.".format(text=text,
                                                  emoji=self._lookup_emoji(emoji)))
        elif text in self.triggers['text_triggers']:
            del self.triggers['text_triggers'][text]
            _save(self.triggers)
            await self.bot.say("Done - I will no longer react to messages containing `{text}`."
                               "".format(text=text))
        else:
            await self.bot.say("Done - no triggers were changed.")

    @trigger_set.command(name="user", pass_context=True)
    async def trigger_set_user(self, ctx, user: discord.User):
        """Trigger if a message is from some user."""
        emoji = await self._get_trigger_emoji(ctx.message.author)
        if emoji:
            self.triggers["user_triggers"][user.id] = emoji
            _save(self.triggers)
            await self.bot.say("Done - I will now react to messages from `{user}` with"
                               " {emoji}.".format(user=str(user),
                                                  emoji=self._lookup_emoji(emoji)))
        elif user.id in self.triggers['user_triggers']:
            del self.triggers['user_triggers'][user.id]
            _save(self.triggers)
            await self.bot.say("Done - I will no longer react to messages from `{user}`."
                               "".format(user=str(user)))
        else:
            await self.bot.say("Done - no triggers were changed.")

    @trigger_set.command(name="list")
    async def trigger_set_list(self):
        """List all active triggers."""
        msg = ''
        if not (self.triggers['text_triggers'] or self.triggers['user_triggers']):
            await self.bot.say('There are no active triggers.')
            return
        if self.triggers['text_triggers']:
            msg += 'These are the active text triggers:\n'
            for text, emoji in self.triggers['text_triggers'].items():
                emoji = self._lookup_emoji(emoji)
                if emoji is None:
                    continue
                msg += '`{text}`: {emoji}\n'.format(text=text, emoji=emoji)
        if self.triggers['user_triggers']:
            msg += 'These are the active user triggers:\n'
            for user_id, emoji in self.triggers['user_triggers'].items():
                user = discord.utils.get(self.bot.get_all_members(), id=user_id)
                emoji = self._lookup_emoji(emoji)
                if user is None or emoji is None:
                    continue
                msg += '`{user}`: {emoji}\n'.format(user=str(user), emoji=emoji)
        for page in pagify(msg):
            await self.bot.say(page)

    async def _get_trigger_emoji(self, user):
        msg = await self.bot.say("React to my message within 15 seconds with"
                                 " the new trigger's emoji!")
        response = await self.bot.wait_for_reaction(timeout=15.0, user=user, message=msg)
        if response:
            emoji = response.reaction.emoji
            if isinstance(emoji, discord.Emoji):
                emoji = emoji.name
            else:
                emoji = name(emoji)
            return emoji

    def _lookup_emoji(self, emoji_name):
        emoji = discord.utils.get(self.bot.get_all_emojis(), name=emoji_name)
        if emoji is None:
            try:
                emoji = lookup(emoji_name)
            except KeyError:
                # Emoji not found; it must have been deleted
                self._delete_triggers(emoji_name)
                return
        return emoji

    def _delete_triggers(self, emoji_name):
        """For cleaning up the json when an emoji is deleted
         and can no longer be found.
        """
        t_trigs_to_del = []
        for text, emoji in self.triggers['text_triggers'].items():
            if emoji == emoji_name:
                t_trigs_to_del.append(text)
        for text in t_trigs_to_del:
            del self.triggers['text_triggers'][text]
        u_trigs_to_del = []
        for user, emoji in self.triggers['user_triggers'].items():
            if emoji == emoji_name:
                u_trigs_to_del.append(user)
        for user in u_trigs_to_del:
            del self.triggers['user_triggers'][user]
        _save(self.triggers)

def _load():
    return dataIO.load_json(TRIGGERS_PATH)

def _save(settings):
    dataIO.save_json(TRIGGERS_PATH, settings)

def _check_folders():
    if not os.path.exists(FOLDER_PATH):
        _LOGGER.info("Creating " + FOLDER_PATH + " folder...")
        os.makedirs(FOLDER_PATH)

def _check_files():
    if not dataIO.is_valid_json(TRIGGERS_PATH):
        _LOGGER.info("Creating json: " + TRIGGERS_PATH)
        dataIO.save_json(TRIGGERS_PATH, DEFAULT_SETTINGS)

def setup(bot: commands.Bot):
    """Load this cog."""
    _check_folders()
    _check_files()
    cog = TriggerReact(bot)
    bot.add_listener(cog.trigger_reactions, "on_message")
    bot.add_cog(cog)
