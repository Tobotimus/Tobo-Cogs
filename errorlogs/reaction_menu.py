import asyncio
import contextlib
import inspect
import itertools
import pathlib
from collections import deque
from typing import Awaitable, Callable, Dict, List

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chatutils, menus as menutils

MAX_CONTENT_SIZE = 2000 - len("```ini```\n\n")


def button(emoji: str):
    def decorator(func):
        try:
            func.__react_to__.append(emoji)
        except AttributeError:
            func.__react_to__ = [emoji]
        return func

    return decorator


# noinspection PyUnusedLocal
class LogScrollingMenu:

    _handlers: Dict[
        str,
        Callable[["LogScrollingMenu", discord.RawReactionActionEvent], Awaitable[None]],
    ] = {}

    def __init__(self, ctx: commands.Context, lines: List[str], page_size: int) -> None:
        self.ctx = ctx
        self.message = None

        self._lines = lines
        self._page_size = page_size
        self._end_pos = len(self._lines)
        self._start_pos = self._end_pos - page_size
        self._done_event = asyncio.Event()

    @classmethod
    async def send(
        cls,
        ctx: commands.Context,
        logfiles: List[pathlib.Path],
        page_size: int = 25,
        num_pages: int = 15,
    ):
        lines = deque(maxlen=num_pages * page_size + 2)
        for logfile_path in logfiles:
            new_lines = deque(maxlen=lines.maxlen - len(lines))
            with logfile_path.open() as fs:
                new_lines.extend(fs.readlines())
            lines = deque(
                iterable=itertools.chain(new_lines, lines), maxlen=lines.maxlen
            )
            del new_lines
            if len(lines) >= lines.maxlen:
                break
        lines.popleft()
        lines.popleft()
        lines.appendleft("# START OF LOG BUFFER\n")
        lines.append("# END OF LOG\n")

        self = cls(ctx, list(lines), page_size)

        self.ctx.bot.add_listener(self.on_raw_reaction, "on_raw_reaction_add")
        self.ctx.bot.add_listener(self.on_raw_reaction, "on_raw_reaction_remove")
        try:
            await asyncio.shield(self.wait())
        except asyncio.CancelledError:
            if not self._done_event.is_set() and self.message is not None:
                with contextlib.suppress(discord.NotFound):
                    await self.message.delete()
        finally:
            self.ctx.bot.remove_listener(self.on_raw_reaction, "on_raw_reaction_add")
            self.ctx.bot.remove_listener(self.on_raw_reaction, "on_raw_reaction_remove")

    async def wait(self) -> None:
        await self._update_message()
        await self._done_event.wait()

    async def on_raw_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        if not self._same_context(payload):
            return

        try:
            handler = self._handlers[payload.emoji.name]
        except KeyError:
            return
        else:
            await handler(self, payload)

    @button("\N{UPWARDS BLACK ARROW}")
    async def scroll_up(self, payload: discord.RawReactionActionEvent) -> None:
        if self._start_pos <= 0:
            return
        self._start_pos -= 1
        self._end_pos = self._start_pos + self._page_size
        await self._update_message(pin="start")

    @button("\N{DOWNWARDS BLACK ARROW}")
    async def scroll_down(self, payload: discord.RawReactionActionEvent) -> None:
        if self._end_pos >= len(self._lines):
            return
        self._end_pos += 1
        self._start_pos = self._end_pos - self._page_size
        await self._update_message(pin="end")

    @button("\N{BLACK UP-POINTING DOUBLE TRIANGLE}")
    async def page_up(self, payload: discord.RawReactionActionEvent) -> None:
        if self._start_pos <= 0:
            return
        self._end_pos = self._start_pos
        self._start_pos = max(self._end_pos - self._page_size, 0)
        await self._update_message(pin="end")

    @button("\N{BLACK DOWN-POINTING DOUBLE TRIANGLE}")
    async def page_down(self, payload: discord.RawReactionActionEvent) -> None:
        if self._end_pos >= len(self._lines):
            return
        self._start_pos = self._end_pos
        self._end_pos = self._start_pos + self._page_size
        await self._update_message(pin="start")

    @button("\N{UP DOWN ARROW}")
    async def expand(self, payload: discord.RawReactionActionEvent) -> None:
        self._page_size += 2
        if self._start_pos <= 0 and self._end_pos >= len(self._lines):
            return
        self._start_pos = max(self._start_pos - 1, 0)
        self._end_pos = min(self._end_pos + 1, len(self._lines))
        await self._update_message()

    @button("\N{END WITH LEFTWARDS ARROW ABOVE}")
    async def go_to_end(self, payload: discord.RawReactionActionEvent) -> None:
        if self._end_pos >= len(self._lines):
            return
        self._end_pos = len(self._lines)
        self._start_pos = self._end_pos - self._page_size
        await self._update_message(pin="end")

    @button("\N{CROSS MARK}")
    async def exit_menu(self, payload: discord.RawReactionActionEvent) -> None:
        self._done_event.set()
        await self.message.delete()

    def _same_context(self, payload: discord.RawReactionActionEvent) -> bool:
        return (
            payload.message_id == self.message.id
            and payload.user_id == self.ctx.author.id
        )

    async def _update_message(self, *, pin: str = "end") -> None:
        joined_lines = "".join(
            self._lines[self._start_pos : self._end_pos]
        )

        if len(joined_lines) > MAX_CONTENT_SIZE:
            if pin == "start":
                cutoff = joined_lines.find("\n", 0, MAX_CONTENT_SIZE)
                joined_lines = joined_lines[:cutoff]
            else:
                cutoff = joined_lines.find("\n", -MAX_CONTENT_SIZE)
                joined_lines = joined_lines[cutoff + 1:]

        rendered_page_size = joined_lines.count("\n")
        if pin == "start":
            self._end_pos = self._start_pos + rendered_page_size
            if self._end_pos >= len(self._lines) and pin == "start":
                while rendered_page_size < self._page_size:
                    try:
                        new_line = self._lines[self._start_pos - 1]
                    except IndexError:
                        break
                    else:
                        if len(joined_lines) + len(new_line) > MAX_CONTENT_SIZE:
                            break
                        joined_lines = new_line + joined_lines
                        self._start_pos -= 1
                        rendered_page_size += 1
        elif pin == "end":
            self._start_pos = self._end_pos - rendered_page_size
            if self._start_pos <= 0 and pin == "end":
                while rendered_page_size < self._page_size:
                    try:
                        new_line = self._lines[self._end_pos]
                    except IndexError:
                        break
                    else:
                        if len(joined_lines) + len(new_line) > MAX_CONTENT_SIZE:
                            break
                        joined_lines += new_line
                        self._end_pos += 1
                        rendered_page_size += 1

        content = chatutils.box(joined_lines, lang="ini")
        if self.message is None:
            self.message = await self.ctx.send(content)
            menutils.start_adding_reactions(self.message, self._handlers.keys())
        else:
            try:
                await self.message.edit(content=content)
            except discord.NotFound:
                self._done_event.set()


for _, _method in reversed(
    inspect.getmembers(LogScrollingMenu, inspect.iscoroutinefunction)
):
    try:
        _emojis = _method.__react_to__
    except AttributeError:
        continue
    else:
        for _emoji in _emojis:
            # noinspection PyProtectedMember
            LogScrollingMenu._handlers[_emoji] = _method
