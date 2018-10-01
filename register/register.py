"""Module for the Register cog."""

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

import discord
from redbot.core import commands


class SelfRole(commands.Converter):
    """Same converter as the one used in Admin, except it grabs the cog differently."""

    async def convert(self, ctx: commands.Context, arg: str) -> discord.Role:
        """Convert an arg to a SelfRole."""
        admin = ctx.bot.get_cog("Admin")
        if admin is None:
            raise commands.BadArgument("Admin is not loaded.")

        conf = admin.conf
        selfroles = await conf.guild(ctx.guild).selfroles()

        role_converter = commands.RoleConverter()
        role = await role_converter.convert(ctx, arg)

        if role.id not in selfroles:
            raise commands.BadArgument("The provided role is not a valid selfrole.")
        return role


class Register(getattr(commands, "Cog", object)):
    """Register - Simplifies two SelfRole commands into one."""

    @commands.command()
    async def register(self, ctx: commands.Context, *, role: SelfRole):
        """Register for a role.

        This command works as an alias for both `[p]selfrole` and `[p]selfrole
        remove`. Which one it aliases depends on whether or not you already have
        the requested role.
        """
        admin_cog = ctx.bot.get_cog("Admin")
        if admin_cog is None:
            await ctx.send("The `admin` cog must be loaded to use this command.")
            return

        if role in ctx.author.roles:
            cmd = admin_cog.selfrole_remove
        else:
            cmd = admin_cog.selfrole

        await ctx.invoke(cmd, selfrole=role)
