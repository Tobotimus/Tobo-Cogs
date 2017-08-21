"""Utility functions for r6pugs."""
import random
import asyncio
import discord
from discord.ext import commands

_ALPHABET_EMOJIS = list(map(chr, range(ord('\N{Regional Indicator Symbol Letter A}'),
                                       ord('\N{Regional Indicator Symbol Letter T}') + 1)))

async def reaction_based_selection(ctx: commands.Context, options_dict: dict, *,
                                   title: str = "Select an option",
                                   option_name: str = "an option",
                                   timeout: float = 15.0):
    """Send a reaction-based selection menu.

    If no option was selected in time, the first option will be returned.

    :return: The option which was selected."""
    options = list(options_dict.keys())
    if len(options) < 2:
        raise ValueError("Must have at least 2 options for a selection menu")
    embed = discord.Embed(title=title,
                          description=("Click the corresponding reaction to select {}."
                                       "".format(option_name)),
                          colour=random_colour())
    try:
        emojis = _ALPHABET_EMOJIS[:len(options)]
    except IndexError:
        raise ValueError("Must not be more than {} options.".format(len(_ALPHABET_EMOJIS)))
    lines = ("{} {}".format(emoji, option) for emoji, option in zip(emojis, options))
    embed.add_field(name="Options", value="\n".join(lines))
    embed.set_footer(text="Only {0.display_name} may select an option.".format(ctx.author))
    menu = await ctx.send(embed=embed)
    for emoji in emojis:
        await menu.add_reaction(emoji)
    try:
        response = await ctx.bot.wait_for(
            "reaction_add", check=lambda r, u: u == ctx.author and r.emoji in emojis,
            timeout=timeout)
    except asyncio.TimeoutError:
        selection = options[0]
    else:
        reaction = response[0]
        selection = options[emojis.index(reaction.emoji)]
    await menu.clear_reactions()
    await menu.edit(content="{} has been selected as {}.".format(selection, option_name),
                    embed=None)
    return options_dict[selection]

def random_colour() -> discord.Colour:
    """Get a random discord colour."""
    rgb = tuple((random.randint(0, 255) for _ in range(3)))
    return discord.Colour.from_rgb(*rgb)
