"""Module for the TriggerReact cog."""
from unicodedata import name, lookup
import discord
from discord.ext.commands import group, guild_only, Context
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import pagify

UNIQUE_ID = 0x774fdb16

class TriggerReact:
    """React to messages based on owner-defined triggers.

    Reactions aren't triggered in PM's."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)

        self.conf.register_global(
            text_triggers={}
        )
        self.conf.register_guild(
            text_triggers={}
        )
        self.conf.register_user(
            emojis=[]
        )
        self.conf.register_member(
            emojis=[]
        )

    async def trigger_reactions(self, message):
        """Fires when the bot sees a message being sent, and
         triggers any reactions.
        """
        if message.author == self.bot.user or isinstance(message.channel,
                                                         discord.abc.PrivateChannel):
            return

        def _triggered_reactions():
            for text, emoji_list in self.conf.text_triggers().items():
                if text in message.content.lower():
                    for emoji in emoji_list:
                        yield self._lookup_emoji(emoji)
            for emoji in self.conf.member(message.author).emojis():
                yield self._lookup_emoji(emoji)
            for emoji in self.conf.user(message.author).emojis():
                yield self._lookup_emoji(emoji)

        for emoji in _triggered_reactions():
            try:
                await message.add_reaction(emoji)
            except (discord.errors.ClientException, discord.errors.HTTPException):
                pass

    @group(name="triggerreact", aliases=["treact"])
    @guild_only()
    @checks.is_owner()
    async def trigger_set(self, ctx: Context):
        """Manage the triggers for reactions. These are global, unless the reaction
         is a server emoji.

        To delete a trigger, reset the trigger with no reaction.
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @trigger_set.command(name="text")
    async def trigger_set_text(self, ctx: Context, *,
                               text: str):
        """Trigger if a message contains a word or phrase.

        This text is not case sensitive and strips the message of leading
         or trailing whitespace.
        """
        text = text.strip().lower()
        emojis = await self._get_trigger_emojis(ctx)
        reply = ''
        if emojis:
            triggers = self.conf.text_triggers()
            triggers[text] = emojis
            await self.conf.set('triggers', triggers)
            emojis_str = " ".join(str(self._lookup_emoji(emoji)) for emoji in emojis)
            reply = ("Done - I will now react to messages containing `{text}` with"
                     " {emojis}.".format(text=text,
                                         emojis=emojis_str))
        elif text in self.conf.text_triggers():
            triggers = self.conf.text_triggers()
            del triggers[text]
            await self.conf.set('triggers', triggers)
            reply = ("Done - I will no longer react to messages containing `{text}`."
                     "".format(text=text))
        else:
            reply = "Done - no triggers were changed."
        await ctx.send(reply)

    @trigger_set.command(name="user", pass_context=True)
    async def trigger_set_user(self, ctx: Context, user: discord.User):
        """Trigger if a message is from some user."""
        emojis = await self._get_trigger_emojis(ctx)
        reply = ''
        if emojis:
            await self.conf.user(user).set('emojis', emojis)
            emojis_str = " ".join(str(self._lookup_emoji(emoji)) for emoji in emojis)
            reply = ("Done - I will now react to messages from `{user}` with"
                     " {emojis}.".format(user=str(user),
                                         emojis=emojis_str))
        else:
            reply = "Done - no triggers were changed."
            if self.conf.user(user).emojis():
                reply = ("Done - I will no longer react to messages from `{user}`."
                         "".format(user=str(user)))
            await self.conf.user(user).set('emojis', [])
        await ctx.send(reply)

    @trigger_set.command(name="list")
    async def trigger_set_list(self, ctx: Context):
        """List all active triggers in your scope."""
        msg = ''
        _text_triggers = self.conf.text_triggers() + self.conf.guild(ctx.guild).text_triggers()
        if _text_triggers:
            msg += 'These are the active text triggers here:'
            for text, emojis in _text_triggers:
                emojis_str = " ".join(str(self._lookup_emoji(emoji)) for emoji in emojis)
                if not emojis_str:
                    continue
                msg += '\n`{text}`: {emojis}'.format(text=text, emojis=emojis_str)
        _member_triggers = self._get_member_triggers(ctx)
        _user_trigger_list = ''
        for user, emojis in self._get_member_triggers(ctx):
            emojis_str = " ".join(str(self._lookup_emoji(emoji)) for emoji in emojis)
            _user_trigger_list += '\n`{user}`: {emojis}'.format(user=str(user), emojis=emojis_str)
        if _user_trigger_list:
            msg += '\nThese are the active user triggers:' + _user_trigger_list
        if not msg:
            ctx.send('There are no reaction triggers here.')
            return
        for page in pagify(msg):
            await ctx.send(page)

    def _get_member_triggers(self, ctx: Context):
        for member in ctx.guild.members:
            emojis = self.conf.member(member).emojis() + self.conf.user(member).emojis()
            if emojis:
                yield (member, emojis)

    async def _get_trigger_emojis(self, ctx: Context):
        """Set up a new trigger."""
        msg = await ctx.send("React to my message with the new trigger's emojis,"
                             " and type `done` when finished.")
        response = await self.bot.wait_for('message',
                                           check=lambda m: (m.author == ctx.author and
                                                            m.channel == ctx.channel and
                                                            'done' in m.content.lower()),
                                           timeout=90.0)
        if response is not None:
            msg = discord.utils.get(self.bot.messages, id=msg.id)
            if msg and msg.reactions:
                emojis = list(_create_emoji_list(msg.reactions))
                return emojis

    def _lookup_emoji(self, emoji_name):
        emoji = discord.utils.get(self.bot.emojis, name=emoji_name)
        if emoji is None:
            try:
                emoji = lookup(emoji_name)
            except KeyError:
                # Emoji not found; it must have been deleted
                return
        return emoji

def _create_emoji_list(reactions):
    for reaction in reactions:
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name
        else:
            emoji = name(emoji)
        yield emoji
