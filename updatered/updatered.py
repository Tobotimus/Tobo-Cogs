"""Module for the UpdateRed cog."""

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

import asyncio
import asyncio.subprocess
import logging
import pathlib
import sys
from typing import Iterable, List, Optional, Tuple

import discord
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import pagify

log = logging.getLogger("red.updatered")


class UpdateRed:
    """Update Red from Discord.

    To get the most out of this cog, run red with the launcher, and use
    the `[p]restart` command to restart the bot after updating.
    """

    DEV_LINK: str = (
        "https://github.com/Cog-Creators/Red-DiscordBot/tarball/"
        "V3/develop#egg=Red-DiscordBot"
    )
    IS_VENV: bool = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    _REDBOT_WIN_EXECUTABLES: List[pathlib.Path] = [
        pathlib.Path("redbot.exe"),
        pathlib.Path("redbot-launcher.exe"),
    ]
    _BIN_PATH: pathlib.Path = pathlib.Path(sys.executable).parent

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    @checks.is_owner()
    @commands.command(aliases=["updatered"])
    async def update(
        self, ctx: commands.Context, version: str = "stable", *extras: str
    ):
        """Update Red with pip.

        The optional `version` argument can be set to any one of the
        following:
         - `stable` (default) - Update to the latest release on PyPI.
         - `pre` - Update to the latest pre-release, if available.
         - `dev` - Update from source control, i.e. V3/develop on
         GitHub.
         - Any specific version, e.g. `3.0.0b19`.

        You may also specify any number of `extras`, which are extra
        requirements you wish to install with Red. For example, to
        update voice and mongo requirements, run the command with
        `[p]update <version> voice mongo`.

        Please note that when specifying any invalid arguments, the cog
        will naively try to run the update command with those arguments,
        possibly resulting in a misleading error message.
        """
        version = version.lower()
        pre = False
        dev = False
        if version == "stable":
            version_marker = ""
        elif version == "pre":
            pre = True
            version_marker = ""
        elif version == "dev":
            dev = True
            version_marker = ""
        else:
            version_marker = "==" + version

        async with ctx.typing():
            return_code, stdout, stderr = await self.update_red(
                version_marker, pre=pre, dev=dev, extras=extras
            )

        if return_code:
            msg = "Something went wrong whilst updating."
        else:
            msg = "Update successful. Restarting your bot is recommended."

        if stdout:
            prompt = await ctx.send(
                msg + " Would you like to see the console output? (y/n)"
            )

            try:
                response: discord.Message = await ctx.bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                response = None

            if response and response.content.lower() in ("y", "yes"):
                await ctx.send_interactive(
                    pagify("\n".join((stdout, stderr))), box_lang=""
                )
            else:
                await prompt.edit(content=msg)
        else:
            await ctx.send(msg)

    async def update_red(
        self,
        version_marker: str,
        pre: bool = False,
        dev: bool = False,
        extras: Optional[Iterable[str]] = None,
    ) -> Tuple[int, str, str]:
        """Update the bot.

        Returns
        -------
        Tuple[int, str, str]
            A tuple in the form (return_code, stdout, stderr).

        """
        if extras:
            extras_str = f"[{','.join(extras)}]"
        else:
            extras_str = ""

        if dev:
            package = self.DEV_LINK + extras_str
        else:
            package = "Red-DiscordBot" + extras_str + version_marker

        args = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            "--no-cache-dir",
            "--process-dependency-links",
        ]
        if pre:
            args.append("--pre")
        if not self.IS_VENV:
            args.append("--user")
        args.append(package)

        if sys.platform == "win32":
            # If we try to update whilst running Red, Windows will throw a permission
            # error.
            self.rename_executables()

        log.debug("Updating Red with command: %s", ' '.join(args))

        process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            loop=self._loop,
        )

        stdout, stderr = await process.communicate()  # Wait for process to finish

        return (
            process.returncode,
            stdout.decode().strip() if stdout else "",
            stderr.decode().strip() if stderr else "",
        )

    @classmethod
    def rename_executables(cls):
        """This is a helper method for renaming Red's executables in Windows."""
        # noinspection PyTypeChecker
        for exe in map(cls._BIN_PATH.joinpath, cls._REDBOT_WIN_EXECUTABLES):
            new_exe = exe.with_suffix(".old")
            if not exe.is_file():
                continue
            log.debug("Renaming %(exe)s to %(new_exe)s...", exe=exe, new_exe=new_exe)
            try:
                exe.rename(new_exe)
            except OSError:
                log.debug("\tRename operation failed!")

    @classmethod
    def cleanup_old_executables(cls):
        # noinspection PyTypeChecker
        for exe in map(cls._BIN_PATH.joinpath, cls._REDBOT_WIN_EXECUTABLES):
            old_exe = exe.with_suffix(".old")
            if not old_exe.is_file():
                continue
            log.debug("Deleting old file %(old_exe)s...", old_exe=old_exe)
            try:
                old_exe.unlink()
            except OSError:
                log.debug("\tDelete operation failed!")
