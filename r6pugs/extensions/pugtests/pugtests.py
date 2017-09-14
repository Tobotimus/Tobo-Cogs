"""Cog for testing this package."""
import discord
from discord.ext import commands
from r6pugs import (TurnBasedVetoMenu, TurnBasedSelectionMenu,
                    PollMenu, ConfirmationMenu, SingleSelectionMenu)

class PugTests:
    """Cog for testing R6Pugs."""

    @commands.command()
    @commands.guild_only()
    async def testconf(self, ctx: commands.Context, *others: discord.Member):
        """Test a confifmation reaction menu."""
        others = list(others)
        others.insert(0, ctx.author)
        menu = ConfirmationMenu(ctx.bot, ctx.channel, others,
                                timeout=8.0)
        selection = await menu.run()
        await ctx.send("Test Complete: {}".format(selection))

    @commands.command()
    async def testsel(self, ctx: commands.Context, n_options: int):
        """Test a selection menu."""
        options = ["Option " + str(idx) for idx in range(1, n_options + 1)]
        menu = SingleSelectionMenu(ctx.bot, ctx.channel, ctx.author,
                                   options, timeout=5.0)
        selection = await menu.run()
        await ctx.send("Test Complete: {}".format(selection))

    @commands.command()
    @commands.guild_only()
    async def testveto(self, ctx: commands.Context, other: discord.Member,
                       n_options: int = 9, n_picks: int = 1):
        """Test a veto reaction menu."""
        options = ["Option " + str(idx) for idx in range(1, n_options + 1)]
        selectors = [ctx.author, other]
        menu = TurnBasedVetoMenu(ctx.bot, ctx.channel, selectors, options,
                                 title="Test Veto",
                                 option_name="an option",
                                 n_picks=n_picks,
                                 selectors_name="vetoers",
                                 timeout=10.0)
        selection = await menu.run()
        await ctx.send("Test Complete: {}".format(selection))

    @commands.command()
    @commands.guild_only()
    async def testpoll(self, ctx: commands.Context, n_options: int = 10, *others: discord.Member):
        """Test a poll reaction menu."""
        options = ["Option " + str(idx) for idx in range(1, n_options + 1)]
        others = list(others)
        others.insert(0, ctx.author)
        menu = PollMenu(ctx.bot, ctx.channel, others, options,
                        title="Test Poll",
                        option_name="an option",
                        timeout=20.0)
        selection = await menu.run()
        await ctx.send("Test Complete: {}".format(selection))

    @commands.command()
    @commands.guild_only()
    async def testtbsel(self, ctx: commands.Context, other: discord.Member,
                        n_options: int = 10):
        """Test a turn-based selection menu."""
        options = ["Option " + str(idx) for idx in range(1, n_options + 1)]
        selectors = [ctx.author, other]
        menu = TurnBasedSelectionMenu(ctx.bot, ctx.channel, selectors, options,
                                      title="Test Turn-based Selection",
                                      option_name="an option",
                                      timeout=10.0)
        selection = await menu.run()
        await ctx.send("Test Complete: {}".format(selection))
