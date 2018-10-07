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
import io
import logging
import pathlib
import re
import sys
import tarfile
import tempfile
import time
from typing import ClassVar, Iterable, List, Optional, Pattern, Tuple

import discord
from redbot.core import checks, commands

log = logging.getLogger("red.updatered")


class UpdateRed(getattr(commands, "Cog", object)):
    """Update Red from Discord.

    To get the most out of this cog, run red with systemd or pm2 on
    Linux, or the launcher on Windows, then use the `[p]restart`
    command to restart the bot after updating.
    """

    DEV_LINK: ClassVar[str] = (
        "https://github.com/Cog-Creators/Red-DiscordBot/tarball/"
        "V3/develop#egg=Red-DiscordBot"
    )
    IS_VENV: ClassVar[bool] = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    _REDBOT_WIN_EXECUTABLES: ClassVar[List[pathlib.Path]] = [
        pathlib.Path("redbot.exe"),
        pathlib.Path("redbot-launcher.exe"),
    ]
    _BIN_PATH: ClassVar[pathlib.Path] = pathlib.Path(sys.executable).parent
    _SAVED_PKG_RE: ClassVar[Pattern[str]] = re.compile(r"\s+Saved\s(?P<path>.*)$")

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    @checks.is_owner()
    @commands.command(aliases=["updatered"])
    async def update(
        self, ctx: commands.Context, version: str = "stable", *extras: str
    ) -> None:
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
            return_code, stdout = await self.update_red(
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
                with io.BytesIO(stdout.encode()) as fp:
                    cur_date = time.strftime("%Y-%m-%dT%H-%M-%S")
                    await ctx.send(
                        file=discord.File(fp, filename=f"updatered-{cur_date}.log")
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
    ) -> Tuple[int, str]:
        """Update the bot.

        Returns
        -------
        Tuple[int, str]
            A tuple in the form (return_code, stdout).

        """
        if extras:
            extras_str = f"[{','.join(extras)}]"
        else:
            extras_str = ""

        if dev:
            package = self.DEV_LINK + extras_str
        else:
            package = "Red-DiscordBot" + extras_str + version_marker

        args = [sys.executable, "-m", "pip", "download", "--no-deps"]
        if pre:
            args.append("--pre")

        args.append(package)

        with tempfile.TemporaryDirectory() as tmpdir:
            args.extend(("-d", str(tmpdir)))

            # Download the Red archive
            log.debug("Downloading Red Archive with command: %s", " ".join(args))
            process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                loop=self._loop,
            )
            stdout_data: bytes = (await process.communicate())[0]
            if stdout_data is not None:
                stdout: str = stdout_data.decode()
            else:
                stdout: str = ""
            if process.returncode:
                return process.returncode, stdout

            for line in stdout.splitlines():
                match = self._SAVED_PKG_RE.match(line)
                if match:
                    archive_path = pathlib.Path(match["path"].strip())
                    break
            else:
                raise RuntimeError("Unexpected output from `pip download`")

            # Rename archive to something universally recognisable.
            # Sometimes the archive name is just "develop" e.g. on a dev update;
            # Pip doesn't like that
            rename_to = archive_path.parent / "Red-DiscordBot.tar.gz"
            archive_path.replace(rename_to)
            archive_path = rename_to

            # Extract dependency_links.txt to install discord.py
            with tarfile.open(archive_path) as archive:
                dep_link = ""
                for member in archive:
                    if member.name.endswith("dependency_links.txt"):
                        with archive.extractfile(member) as file:
                            dep_link = file.readline().decode()
                            break
                else:
                    raise RuntimeError("No dependency_links.txt found!")

            # Remove trailing version number in egg link
            # For some reason it creates a bunch of weird shit in stdout
            end_str_idx = dep_link.rfind("#egg=discord.py") + len("#egg=discord.py")
            dep_link = dep_link[:end_str_idx]

            args = (sys.executable, "-m", "pip", "install", "--upgrade", dep_link)
            log.debug("Installing discord.py with command: %s", " ".join(args))
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                loop=self._loop,
            )

            stdout_data = (await process.communicate())[0]
            if stdout_data is not None:
                stdout += "\n" + stdout_data.decode()
            if process.returncode:
                return process.returncode, stdout

            if sys.platform == "win32":
                # If we try to update whilst running Red, Windows will throw a permission
                # error.
                self.rename_executables()

            args = (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                str(archive_path),
            )
            log.debug("Installing Red package with command: %s", " ".join(args))

            process = None
            try:
                # Install package itself
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    loop=self._loop,
                )

                stdout_data = (await process.communicate())[0]
                if stdout_data is not None:
                    stdout += "\n" + stdout_data.decode()
            finally:
                if sys.platform == "win32" and process and process.returncode:
                    self.undo_rename_executables()

        return process.returncode, stdout

    @classmethod
    def rename_executables(cls) -> None:
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
                log.error(
                    "Failed to rename %(exe)s to $(new_exe)s!", exe=exe, new_exe=new_exe
                )

    @classmethod
    def undo_rename_executables(cls) -> None:
        # noinspection PyTypeChecker
        for exe in map(cls._BIN_PATH.joinpath, cls._REDBOT_WIN_EXECUTABLES):
            old_exe = exe.with_suffix(".old")
            if not old_exe.is_file():
                continue
            log.debug("Renaming %(exe)s to %(new_exe)s...", exe=old_exe, new_exe=exe)
            try:
                old_exe.rename(exe)
            except OSError:
                log.error(
                    "Failed to rename %(exe)s to $(new_exe)s!", exe=old_exe, new_exe=exe
                )

    @classmethod
    def cleanup_old_executables(cls) -> None:
        # noinspection PyTypeChecker
        for exe in map(cls._BIN_PATH.joinpath, cls._REDBOT_WIN_EXECUTABLES):
            old_exe = exe.with_suffix(".old")
            if not old_exe.is_file():
                continue
            log.debug("Deleting old file %(old_exe)s...", old_exe=old_exe)
            try:
                old_exe.unlink()
            except OSError:
                log.debug("Failed to delete old file %(old_exe)s!", old_exe=old_exe)
