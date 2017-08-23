"""Utility functions for r6pugs."""
import random
import asyncio
from datetime import datetime
from typing import Tuple, List, Union
import discord
from discord.ext import commands
from core.utils.chat_formatting import box
from .errors import MenuNotSent
from .log import LOG

class _ReactionMenu:

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel):
        self.bot = bot
        self.channel = channel
        self.message = None

    async def wait_for_reaction(self, *,
                                users: List[discord.User]=None,
                                emojis: List[Union[discord.Emoji, str]],
                                check=None,
                                timeout: float = None):
        """Wait for a reaction which meets the passed in requirements.

        The menu must have been sent before calling."""
        if self.message is None:
            raise MenuNotSent("The menu must be sent before waiting for a reaction.")
        def _check(reaction: discord.Reaction, user: discord.User):
            message_check = reaction.message.id == self.message.id
            user_check = users is None or user in users
            emoji_check = emojis is None or reaction.emoji in emojis
            check_check = check is None or check(reaction, user)
            return message_check and user_check and emoji_check and check_check
        return await self.bot.wait_for("reaction_add", check=_check, timeout=timeout)

class ConfirmationMenu(_ReactionMenu):
    """Confirmation menu where users can tick a box to confirm something."""

    TICK = '\N{White Heavy Check Mark}'
    CROSS = '\N{Negative Squared Cross Mark}'

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 members: List[discord.Member], **attrs):
        self.members = members
        self.title = attrs.pop("title", "Confirmation")
        self.action = attrs.pop("action", "confirm")
        self.timeout = attrs.pop("timeout", 120.0)
        super().__init__(bot, channel)

    async def run(self):
        """Send the menu. Returns the list of members who did not confirm."""
        members = self.members
        timeout = self.timeout
        if not members:
            raise ValueError("members must not be empty")
        embed = discord.Embed(title=self.title,
                              description=("Click the reaction below to {}. You have {} seconds."
                                           "".format(self.action, int(timeout))),
                              colour=random_colour())
        lines = ("{} {}".format(self.CROSS, member.display_name) for member in members)
        embed.add_field(name="Players", value="\n".join(lines))
        self.message = await self.channel.send(embed=embed)
        await self.message.add_reaction(self.TICK)
        iterations = len(members)
        started = datetime.now()
        time_passed = 0
        for _ in range(len(iterations)):
            try:
                response = await self.wait_for_reaction(users=members,
                                                        emojis=[self.TICK],
                                                        timeout=timeout-time_passed)
            except asyncio.TimeoutError:
                reaction = discord.utils.get(self.message.reactions, emoji=self.TICK)
                reacted = await reaction.users.flatten()
                if all(member in reacted for member in members):
                    return []
                return list(filter(lambda m: m not in reacted, members))
            else:
                member = response[1]
                members.remove(member)
                await self._confirm(member)
                if not members:
                    return []
                time_passed = (datetime.now() - started).seconds()
        return []

    async def _confirm(self, member: discord.Member):
        if self.message is None:
            return
        embed = self.message.embeds[0]
        members_str = embed.fields[0].value
        lines = members_str.split('\n')
        for idx, line in enumerate(lines):
            if member.display_name in line:
                lines[idx] = "{} {}".format(self.TICK, member.display_name)
                break
        embed.set_field_at(0, value="\n".join(lines))
        await self.message.edit(embed=embed)

class _OptionMenu(_ReactionMenu):

    # Emoji list can only go up to T, due to the limit of how many
    #  reactions can be added to a discord message.
    ALPHABET_EMOJIS = list(map(chr, range(ord('\N{Regional Indicator Symbol Letter A}'),
                                          ord('\N{Regional Indicator Symbol Letter T}') + 1)))

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 options: List[str], **attrs):
        self.options = options
        self.title = attrs.pop("title", "Option Menu")
        self.option_name = attrs.pop("option_name", "an option")
        self.timeout = attrs.pop("timeout", 30.0)
        super().__init__(bot, channel)

    def get_embed(self):
        """Get the embed for this option menu.

        Returns a tuple in the form `(emojis, embed)`, emojis being a list
         of emojis used in the option menu.
        """
        embed = discord.Embed(title=self.title,
                              description=("Click the corresponding reaction to select {}."
                                           "".format(self.option_name)),
                              colour=random_colour())
        try:
            emojis = self.ALPHABET_EMOJIS[:len(self.options)]
        except IndexError:
            raise ValueError("Must not be more than {} options.".format(len(self.ALPHABET_EMOJIS)))
        lines = ("{} {}".format(emoji, option) for emoji, option in zip(emojis, self.options))
        embed.add_field(name="Options", value="\n".join(lines))
        return (emojis, embed)

class SingleSelectionMenu(_OptionMenu):
    """Selection menu where a user gets to pick one option."""

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 selector: discord.Member, options: List[str], **attrs):
        self.selector = selector
        super().__init__(bot, channel, options, **attrs)

    async def run(self):
        """Send the selection menu and wait for the user to select an option."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 2 options for a selection menu")
        (emojis, embed) = self.get_embed()
        embed.set_footer(text=("Only **{0.display_name}** may select {1}"
                               "".format(self.selector, self.option_name)))
        self.message = await self.channel.send(embed=embed)
        for emoji in emojis:
            await self.message.add_reaction(emoji)
        try:
            response = await self.wait_for_reaction(users=[self.selector],
                                                    emojis=emojis,
                                                    timeout=self.timeout)
        except asyncio.TimeoutError:
            return
        else:
            LOG.debug("Got reaction")
            reaction = response[0]
            selection = self.options[emojis.index(reaction.emoji)]
            await self.finish(selection)
        return selection

    async def finish(self, selection: str):
        """Edit the result into the message."""
        await self.message.clear_reactions()
        await self.message.edit(content=("**{}** has been selected as {}."
                                         "".format(selection, self.option_name)),
                                embed=None)

class _TurnBasedMenu(_OptionMenu):

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 selectors: Tuple[discord.Member], options: List[str],
                 **attrs):
        self.selectors = selectors
        self.selectors_name = attrs.pop("selectors_name", "selectors")
        super().__init__(bot, channel, options, **attrs)

    async def take_turns(self, iterations: int, emojis: List[str], callback, *,
                         double_turns: bool = False) -> List[str]:
        """Take turns picking options and then doing whatever the `callback` is."""
        cur_turn = 0
        turns_left = 1
        selector = None
        for _ in range(iterations):
            turns_left -= 1
            selector = self.selectors[cur_turn]
            if len(self.options) == 1:
                await callback(self.options.pop(), selector, emojis.pop())
                break
            await self._update_footer(selector)
            response = self._get_response(selector, emojis)
            await callback(*response)
            if turns_left == 0:
                cur_turn = int(not cur_turn)
                if double_turns:
                    turns_left = 2

    async def _update_footer(self, selector: discord.Member):
        embed = self.message.embeds[0]
        embed.set_footer(text=("{0.display_name}'s turn to select {1}."
                               "".format(selector, self.option_name)))
        await self.message.edit(embed=embed)

    async def _get_response(self, selector: discord.Member,
                            emojis: List[str]) -> Tuple[str, discord.Member, str]:
        try:
            response = await self.wait_for_reaction(users=[selector],
                                                    emojis=emojis,
                                                    timeout=self.timeout)
        except asyncio.TimeoutError:
            selection = random.choice(self.options)
            idx = self.options.index(selection)
            emoji = emojis.pop(idx)
        else:
            reaction = response[0]
            idx = emojis.index(reaction.emoji)
            selection = self.options[idx]
            emoji = emojis.pop(idx)
        return (selection, selector, emoji)

    async def _update_option(self, option: str, selector: discord.Member, *,
                             old_emoji: str = None,
                             new_emoji: str = None,
                             action: str = None):
        if old_emoji is not None:
            reaction = discord.utils.get(self.message.reactions, emoji=old_emoji)
            if reaction is not None:
                async for member in reaction.members:
                    await self.message.remove_reaction(old_emoji, member)
        embed = self.message.embeds[0]
        options_str = embed.fields[0].value
        lines = options_str.split('\n')
        idx = self.options.index(option)
        selector = str(selector) if selector is None else selector.display_name
        lines[idx] = ("{0} ~~{1}~~ *{2}ed by {3}*"
                      "".format(new_emoji, option, action, selector))
        embed.set_field_at(0, value="\n".join(lines))
        await self.message.edit(embed=embed)

class TurnBasedVetoMenu(_TurnBasedMenu):
    """A veto menu where two users take turns vetoing through a list
     of options, until `n_picks` are remaning."""

    VETOED = '\N{No Entry}'
    PICKED = '\N{White Heavy Check Mark}'

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 selectors: Tuple[discord.Member], options: List[str],
                 **attrs):
        self.n_picks = attrs.pop("n_picks", 1)
        self.picks = []
        super().__init__(bot, channel, options, **attrs)

    async def run(self):
        """Send the veto menu and let the selectors take turns vetoing."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 3 options for a turn-based menu")
        if self.n_picks > len(self.options) + 1:
            raise ValueError("Must have at least 2 more options than picks.")
        (emojis, embed) = self.get_embed()
        self.message = await self.channel.send(
            content=("{0[0].mention} and {0[1].mention} are the {1}."
                     "".format(self.selectors, self.selectors_name)),
            embed=embed)
        for emoji in emojis:
            await self.message.add_reaction(emoji)
        emojis = await self._run_veto(emojis)
        await self._run_picks(emojis)
        picks_str = box('\n'.join(self.picks), lang="diff")
        await self.message.edit(
            content=("The {} has been completed, these are the remaining {}s:"
                     "{}".format(self.title, self.option_name, picks_str)),
            embed=None)
        return self.picks

    async def _run_veto(self, emojis: List[str]) -> List[str]:
        iterations = len(emojis) - self.n_picks - (len(emojis) % 2)
        await self.take_turns(iterations, emojis, self.veto)
        return emojis

    async def _run_picks(self, emojis: List[str]):
        iterations = self.n_picks - (self.n_picks % 2)
        await self.take_turns(iterations, emojis, self.pick)
        if self.n_picks > 0 and self.options:
            await self.pick(self.options.pop(), None, emojis.pop())

    async def veto(self, option: str, selector: discord.Member, emoji: str = None):
        """Veto an option from this menu."""
        await self._update_option(option, selector,
                                  old_emoji=emoji, new_emoji=self.VETOED,
                                  action="veto")
        self.options.remove(option)

    async def pick(self, option: str, selector: discord.Member, emoji: str = None):
        """Pick an option from this menu."""
        await self._update_option(option, selector,
                                  old_emoji=emoji, new_emoji=self.PICKED,
                                  action="pick")
        self.picks.append(option)
        self.n_picks -= 1

class TurnBasedSelectionMenu(_TurnBasedMenu):
    """A selection menu where two users take turns selecting from
     a list until the list is exhausted
    """

    SELECTED = (
        '\N{Large Blue Diamond}',
        '\N{Large Orange Diamond}'
    )

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel,
                 selectors: Tuple[discord.Member], options: List[str],
                 **attrs):
        if len(options) % 2 != 0:
            raise ValueError("Must be even number of options.")
        self.selections = ([], [])
        super().__init__(bot, channel, options, **attrs)

    async def run(self):
        """Send the selections menu and let the selectors take turns picking."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 3 options for a turn-based menu")
        (emojis, embed) = self.get_embed()
        self.message = await self.channel.send(
            content=("{0[0].mention} and {0[1].mention} are the {1}."
                     "".format(self.selectors, self.selectors_name)),
            embed=embed)
        for emoji in emojis:
            await self.message.add_reaction(emoji)
        await self._run_selections(emojis)
        picks_strs = [box('\n'.join(s), lang="diff") for s in self.selections]
        embed = discord.Embed(title=self.title,
                              description="Complete",
                              colour=embed.colour)
        embed.add_field(name="Blue Team", value=picks_strs[0])
        embed.add_field(name="Orange Team", value=picks_strs[1])
        await self.message.edit(embed=embed)
        return self.selections

    async def _run_selections(self, emojis: List[str]):
        iterations = len(self.options)
        await self.take_turns(iterations, emojis, self.select, double_turns=True)

    async def select(self, option: str, selector: discord.Member, emoji: str = None):
        """Select an option from this menu."""
        new_emoji = self.SELECTED[self.selectors.index(selector)]
        await self._update_option(option, selector,
                                  old_emoji=emoji, new_emoji=new_emoji,
                                  action="pick")
        idx = self.selectors.index(selector)
        self.selections[idx].append(option)
        self.options.remove(option)

def random_colour() -> discord.Colour:
    """Get a random discord colour."""
    rgb = tuple((random.randint(0, 255) for _ in range(3)))
    return discord.Colour.from_rgb(*rgb)
