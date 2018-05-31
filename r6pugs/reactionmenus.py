"""Utility functions for r6pugs."""

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

import random
import asyncio
from datetime import datetime
from typing import Tuple, List, Union
from collections import Counter
import discord
from discord.ext import commands
from redbot.core.utils.chat_formatting import box
from .errors import MenuNotSent

__all__ = [
    "ConfirmationMenu",
    "SingleSelectionMenu",
    "PollMenu",
    "TurnBasedVetoMenu",
    "TurnBasedSelectionMenu",
]


class _ReactionMenu:
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel):
        self.bot = bot
        self.channel = channel
        self.message = None

    async def wait_for_reaction(
        self,
        *,
        users: List[discord.User] = None,
        emojis: List[Union[discord.Emoji, str]],
        check=None,
        timeout: float = None
    ):
        """Wait for a reaction which meets the passed in requirements.

        The menu must have been sent before calling.
        """
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

    TICK = "\N{White Heavy Check Mark}"
    CROSS = "\N{Negative Squared Cross Mark}"

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        members: List[discord.Member],
        **attrs
    ):
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
        embed = discord.Embed(
            title=self.title,
            description=(
                "Click the reaction below to {}. You have {} seconds."
                "".format(self.action, int(timeout))
            ),
            colour=random_colour(),
        )
        lines = ("{} {}".format(self.CROSS, member.display_name) for member in members)
        embed.add_field(name="Players", value="\n".join(lines))
        self.message = await self.channel.send(embed=embed)
        await self.message.add_reaction(self.TICK)
        iterations = len(members)
        started = datetime.now()
        time_passed = 0
        for _ in range(iterations):
            try:
                response = await self.wait_for_reaction(
                    users=members, emojis=[self.TICK], timeout=timeout - time_passed
                )
            except asyncio.TimeoutError:
                self.message = await self.channel.get_message(self.message.id)
                reaction = discord.utils.get(self.message.reactions, emoji=self.TICK)
                if reaction is not None:
                    reacted = await reaction.users().flatten()
                    if all(member in reacted for member in members):
                        return []
                    return list(filter(lambda m: m not in reacted, members))
                else:
                    return members
            else:
                member = response[1]
                members.remove(member)
                await self._confirm(member)
                if not members:
                    return []
                time_passed = (datetime.now() - started).seconds
        return []

    async def _confirm(self, member: discord.Member):
        if self.message is None:
            return
        embed = self.message.embeds[0]
        members_str = embed.fields[0].value
        lines = members_str.split("\n")
        for idx, line in enumerate(lines):
            if member.display_name in line:
                lines[idx] = "{} {}".format(self.TICK, member.display_name)
                break
        embed.set_field_at(0, name="Options", value="\n".join(lines))
        await self.message.edit(embed=embed)


class _OptionMenu(_ReactionMenu):

    # Emoji list can only go up to T, due to the limit of how many
    #  reactions can be added to a discord message.
    ALPHABET_EMOJIS = list(
        map(
            chr,
            range(
                ord("\N{Regional Indicator Symbol Letter A}"),
                ord("\N{Regional Indicator Symbol Letter T}") + 1,
            ),
        )
    )

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        options: List[str],
        **attrs
    ):
        self.options = options
        self.title = attrs.pop("title", "Option Menu")
        self.option_name = attrs.pop("option_name", "an option")
        self.timeout = attrs.pop("timeout", 30.0)
        try:
            self.emojis = self.ALPHABET_EMOJIS[: len(self.options)]
        except IndexError:
            raise ValueError(
                "Must not be more than {} options.".format(len(self.ALPHABET_EMOJIS))
            )
        super().__init__(bot, channel)

    def get_embed(self):
        """Get the embed for this option menu."""
        embed = discord.Embed(
            title=self.title,
            description=(
                "Click the corresponding reaction to select {}."
                "".format(self.option_name)
            ),
            colour=random_colour(),
        )
        lines = (
            "{} {}".format(emoji, option)
            for emoji, option in zip(self.emojis, self.options)
        )
        embed.add_field(name="Options", value="\n".join(lines))
        return embed

    async def setup_reactions(self):
        """Add the reactions to this menu."""
        for emoji in self.emojis:
            await self.message.add_reaction(emoji)


class SingleSelectionMenu(_OptionMenu):
    """Selection menu where a user gets to pick one option."""

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        selector: discord.Member,
        options: List[str],
        **attrs
    ):
        self.selector = selector
        super().__init__(bot, channel, options, **attrs)

    async def run(self):
        """Send the selection menu and wait for the user to select an option."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 2 options for a selection menu")
        embed = self.get_embed()
        embed.set_footer(
            text=(
                "Only {0.display_name} may select {1}"
                "".format(self.selector, self.option_name)
            )
        )
        self.message = await self.channel.send(embed=embed)
        await self.setup_reactions()
        try:
            response = await self.wait_for_reaction(
                users=[self.selector], emojis=self.emojis, timeout=self.timeout
            )
        except asyncio.TimeoutError:
            return
        else:
            reaction = response[0]
            selection = self.options[self.emojis.index(reaction.emoji)]
            await self.finish(selection)
        return selection

    async def finish(self, selection: str):
        """Edit the result into the message."""
        await self.message.clear_reactions()
        await self.message.edit(
            content=(
                "**{}** has been selected as {}." "".format(selection, self.option_name)
            ),
            embed=None,
        )


class PollMenu(_OptionMenu):
    """A poll menu, where a group of users can vote on some list of options."""

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        voters: List[discord.Member],
        options: List[str],
        **attrs
    ):
        self.voters = voters
        self.votes = Counter()
        super().__init__(bot, channel, options, **attrs)

    async def run(self):
        """Send the poll menu and wait for the users to vote."""
        if len(self.options) < 2 or len(self.voters) < 2:
            raise ValueError("Must have at least 2 options/voters for a poll menu")
        embed = self.get_embed()
        self.message = await self.channel.send(embed=embed)
        await self.setup_reactions()
        started = datetime.now()
        time_passed = 0
        for _ in range(len(self.voters)):
            try:
                response = await self.wait_for_reaction(
                    users=self.voters,
                    emojis=self.emojis,
                    timeout=self.timeout - time_passed,
                )
            except asyncio.TimeoutError:
                break
            else:
                await self.vote(*response)
                time_passed = (datetime.now() - started).seconds
        return await self.finish()

    async def vote(self, reaction: discord.Reaction, voter: discord.Member):
        """Register a user's vote with a reaction."""
        if voter in self.voters:
            self.voters.remove(voter)
        vote = self.options[self.emojis.index(reaction.emoji)]
        self.votes[vote] += 1

    async def finish(self):
        """Edit the result into the message."""
        await self.message.clear_reactions()
        if self.votes:
            selection = self.votes.most_common(1)[0][0]
        else:
            selection = random.choice(self.options)
        await self.message.edit(
            content=(
                "**{}** has been voted as {}." "".format(selection, self.option_name)
            ),
            embed=None,
        )
        return selection


class _TurnBasedMenu(_OptionMenu):
    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        selectors: Tuple[discord.Member],
        options: List[str],
        **attrs
    ):
        self.selectors = selectors
        self.selectors_name = attrs.pop("selectors_name", "selectors")
        super().__init__(bot, channel, options, **attrs)
        self.remainder = dict(zip(self.emojis, self.options))

    async def take_turns(
        self,
        iterations: int,
        callback,
        *,
        double_turns: bool = False,
        action: str = "select"
    ):
        """Take turns picking options and then doing whatever the `callback` is."""
        cur_turn = 0
        turns_left = 1
        selector = None
        for _ in range(iterations):
            turns_left -= 1
            selector = self.selectors[cur_turn]
            if len(self.remainder) == 1:
                await callback(next(iter(self.remainder.keys())), selector)
                break
            await self._update_footer(selector, action)
            response = await self._get_response(selector, list(self.remainder.keys()))
            await callback(*response)
            if turns_left == 0:
                cur_turn = int(not cur_turn)
                if double_turns:
                    turns_left = 2
                else:
                    turns_left = 1

    async def _update_footer(self, selector: discord.Member, action: str = "select"):
        embed = self.message.embeds[0]
        embed.set_footer(
            text=(
                "{0.display_name}'s turn to {1} {2}."
                "".format(selector, action, self.option_name)
            )
        )
        await self.message.edit(embed=embed)

    async def _get_response(self, selector: discord.Member, emojis: List[str]):
        try:
            response = await self.wait_for_reaction(
                users=[selector], emojis=emojis, timeout=self.timeout
            )
        except asyncio.TimeoutError:
            emoji = random.choice(emojis)
        else:
            reaction = response[0]
            emoji = reaction.emoji
        return (emoji, selector)

    async def _update_option(
        self,
        option: str,
        selector: discord.Member,
        *,
        old_emoji: str = None,
        new_emoji: str = None,
        action: str = None
    ):
        embed = self.message.embeds[0]
        options_str = embed.fields[0].value
        lines = options_str.split("\n")
        idx = self.options.index(option)
        selector = "me" if selector is None else selector.display_name
        lines[idx] = "{0} ~~{1}~~ *{2}ed by {3}*" "".format(
            new_emoji, option, action, selector
        )
        embed.set_field_at(0, name="Options", value="\n".join(lines))
        await self.message.edit(embed=embed)
        # Possibly clear the reaction
        if old_emoji is not None:
            self.message = await self.channel.get_message(self.message.id)
            reaction = next(
                (r for r in self.message.reactions if r.emoji == old_emoji), None
            )
            if reaction is not None:
                async for member in reaction.users():
                    await self.message.remove_reaction(old_emoji, member)


class TurnBasedVetoMenu(_TurnBasedMenu):
    """A veto menu where two users take turns vetoing.

    The users vetothrough a list of options, until `n_picks` are remaning.
    Then, the users will take turns selecting the remaining options.
    """

    VETOED = "\N{No Entry}"
    PICKED = "\N{White Heavy Check Mark}"

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        selectors: Tuple[discord.Member],
        options: List[str],
        **attrs
    ):
        self.n_picks = attrs.pop("n_picks", 1)
        self.picks = []
        super().__init__(bot, channel, selectors, options, **attrs)

    async def run(self):
        """Send the veto menu and let the selectors take turns vetoing."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 3 options for a turn-based menu")
        if self.n_picks > len(self.options) + 1:
            raise ValueError("Must have at least 2 more options than picks.")
        embed = self.get_embed()
        self.message = await self.channel.send(
            content=(
                "{0[0].mention} and {0[1].mention} are the {1}."
                "".format(self.selectors, self.selectors_name)
            ),
            embed=embed,
        )
        await self.setup_reactions()
        await self._run_veto()
        await self._run_picks()
        picks_str = box("\n".join(self.picks), lang="diff")
        await self.message.edit(
            content=(
                "The {} has been completed, these are the remaining {}s:"
                "{}".format(self.title, self.option_name, picks_str)
            ),
            embed=None,
        )
        await self.message.clear_reactions()
        return self.picks

    async def _run_veto(self) -> List[str]:
        iterations = len(self.emojis) - self.n_picks
        iterations -= iterations % 2
        await self.take_turns(iterations, self.veto, action="veto")

    async def _run_picks(self):
        iterations = self.n_picks
        await self.take_turns(iterations, self.pick, action="pick")
        if self.n_picks > 0 and self.remainder:
            await self.pick(next(iter(self.remainder.keys())))

    async def veto(self, emoji: str, selector: discord.Member = None):
        """Veto an option from this menu by its corresponding emoji."""
        option = self.remainder.pop(emoji)
        await self._update_option(
            option, selector, old_emoji=emoji, new_emoji=self.VETOED, action="veto"
        )

    async def pick(self, emoji: str, selector: discord.Member = None):
        """Pick an option from this menu by its corresponding emoji."""
        option = self.remainder.pop(emoji)
        await self._update_option(
            option, selector, old_emoji=emoji, new_emoji=self.PICKED, action="pick"
        )
        self.picks.append(option)
        self.n_picks -= 1


class TurnBasedSelectionMenu(_TurnBasedMenu):
    """A selection menu where two users take turns selecting.

    Users select from a list of options until the list is exhausted.
    """

    SELECTED = ("\N{Large Blue Diamond}", "\N{Large Orange Diamond}")

    def __init__(
        self,
        bot: commands.Bot,
        channel: discord.TextChannel,
        selectors: Tuple[discord.Member],
        options: List[str],
        **attrs
    ):
        if len(options) % 2 != 0:
            raise ValueError("Must be even number of options.")
        self.selections = ([], [])
        super().__init__(bot, channel, selectors, options, **attrs)

    async def run(self):
        """Send the selections menu and let the selectors take turns picking."""
        if len(self.options) < 2:
            raise ValueError("Must have at least 3 options for a turn-based menu")
        embed = self.get_embed()
        self.message = await self.channel.send(
            content=(
                "{0[0].mention} and {0[1].mention} are the {1}."
                "".format(self.selectors, self.selectors_name)
            ),
            embed=embed,
        )
        await self.setup_reactions()
        await self._run_selections()
        picks_strs = [box("\n".join(s), lang="diff") for s in self.selections]
        embed = discord.Embed(
            title=self.title, description="Complete", colour=embed.colour
        )
        for idx, selector in enumerate(self.selectors):
            embed.add_field(
                name="{0.display_name}'s Picks".format(selector), value=picks_strs[idx]
            )
        await self.message.edit(embed=embed)
        return self.selections

    async def _run_selections(self):
        iterations = len(self.options)
        await self.take_turns(iterations, self.select, double_turns=True)

    async def select(self, emoji: str, selector: discord.Member):
        """Select an option from this menu by its emoji."""
        new_emoji = self.SELECTED[self.selectors.index(selector)]
        option = self.remainder.pop(emoji)
        await self._update_option(
            option, selector, old_emoji=emoji, new_emoji=new_emoji, action="pick"
        )
        idx = self.selectors.index(selector)
        self.selections[idx].append(option)


def random_colour() -> discord.Colour:
    """Get a random discord colour."""
    rgb = tuple((random.randint(0, 255) for _ in range(3)))
    return discord.Colour.from_rgb(*rgb)
