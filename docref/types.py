"""Module containing various classes used in docref."""
import re
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union

from redbot.core import commands

from .errors import InternalError, NoMoreRefs

__all__ = (
    "NodeRef",
    "RawRefSpec",
    "RefSpec",
    "RawInvMetaData",
    "InvMetaData",
    "RawRefDict",
    "RefDict",
    "RawInvData",
    "InvData",
    "FilterFunc",
    "MatchesDict",
)


class RefSpec(NamedTuple):
    """Container for data relating to a reference.

    This class is simply a `collections.namedtuple`, and thus it is immutable.

    Attributes
    ----------
    url : str
        A direct URL to the reference.
    display_name : str
        The reference's display name (often the same as the normal reference
        name.

    """

    url: str
    display_name: str


class InvMetaData:
    """Metadata for a sphinx inventory."""

    __slots__ = ("_projname", "_version", "_refcount")

    def __init__(self, projname: str, version: str, refcount: int = 0):
        self._projname: str = projname
        self._version: str = version
        self._refcount: int = refcount

    @property
    def projname(self) -> str:
        """(str) : The name of the project which contains this inventory."""
        return self._projname

    @property
    def version(self) -> str:
        """(str) : The version of the project."""
        return self._version

    @property
    def refcount(self) -> int:
        """(int) : The reference count for this inventory."""
        return self._refcount

    def inc_refcount(self) -> None:
        """Increment this inventory's refcount."""
        self._refcount += 1

    def dec_refcount(self) -> None:
        """Decrement this inventory's refcount.

        Raises
        ------
        NoMoreRefs
            If the refcount has reached zero.

        """
        self._refcount -= 1
        if self._refcount == 0:
            raise NoMoreRefs()
        if self._refcount < 0:
            raise InternalError("Tried to decref on an inventory with no refs.")

    def to_dict(self) -> "RawInvMetaData":
        """Return this metadata object as a dict."""
        return {
            "projname": self.projname,
            "version": self.version,
            "refcount": self.refcount,
        }

    def __eq__(self, other: Any) -> bool:
        """Check if this metadata object is equal to another.

        Returns
        -------
        bool
            ``True`` if `projname` and `version` match.

        """
        if not isinstance(other, self.__class__):
            return False
        return self.projname == other.projname and self.version == other.version

    def __ne__(self, other: Any) -> bool:
        """Check if this metadata object is not equal to another.

        Returns
        -------
        bool
            ``False`` if `projname` and `version` match.

        """
        return not self.__eq__(other)

    def __str__(self) -> str:
        """Get a string representation of this metadata.

        Returns
        -------
        str
            ``{projname} {version}``

        """
        return f"{self.projname} {self.version}"


class NodeRef:
    """Class for a reference to a sphinx node.

    Attributes
    ----------
    refname : str
        The reference name to search for.
    role : str
        The role for the reference. Can be ``"any"`` to be totally ambiguous.
    lang : Optional[str]
        The language to match the role. ``None`` if omitted - this is not
        often needed.

    """

    REF_PATTERN = re.compile(
        r"(?P<dir1>:[a-z\-]+:)?(?P<dir2>[a-z\-]+:)?`?(?P<refname>.*)`?$"
    )
    STD_ROLES = ("doc", "label", "term", "cmdoption", "envvar", "opcode", "token")

    def __init__(self, refname: str, role: str, lang: Optional[str]):
        self.refname: str = refname.strip()
        self.role: str = role
        self.lang: Optional[str] = lang

    @classmethod
    async def convert(cls, ctx: commands.Context, argument: str) -> "NodeRef":
        """Convert from a string argument to a NodeRef."""
        argument = argument.strip("`")

        match = cls.REF_PATTERN.match(argument)
        # make sure the refname exists
        refname = match["refname"]
        if refname is None:
            raise commands.BadArgument(
                f'Failed to parse reference "{argument}" - '
                f"see `{ctx.prefix}help {ctx.invoked_with}` for details."
            )
        # try to line up the lang:role syntax
        if match["dir1"] and match["dir2"]:
            lang = match["dir1"].strip(":")
            role = match["dir2"].strip(":")
        else:
            lang = None
            if match["dir1"]:
                role = match["dir1"].strip(":")
            elif match["dir2"]:
                role = match["dir2"].strip(":")
            else:
                role = "any"

        if role in cls.STD_ROLES:
            lang = "std"

        return cls(refname, role, lang)

    @property
    def reftype(self) -> str:
        """(str) : Get this reference's full directive as ``lang:role``."""
        if self.lang is None:
            return f"{self.role}"
        else:
            return f"{self.lang}:{self.role}"

    def __str__(self) -> str:
        """Get a string representation of this node reference.

        Returns
        -------
        str
            ``:lang:role:`refname```.

        """
        return f":{self.reftype}:`{self.refname}`"

    def __repr__(self) -> str:
        """Get a string representation suitable for debugging.

        Returns
        -------
        str
            ``<NodeRef refname=refname role=role lang=lang>``

        """
        return (
            f"<NodeRef refname={self.refname!r} role={self.role!r} lang={self.lang!r}>"
        )


# These are just for type-hints

RawInvMetaData = Dict[str, Union[str, int]]
# {"projname": str, "version" : str, "refcount": int}

RawRefSpec = Tuple[str, str, str, str]
# (projname, version, url, display_name)

RawRefDict = Dict[str, RawRefSpec]
RefDict = Dict[str, RefSpec]
# {refname: refspec}

RawInvData = Dict[str, RawRefDict]
InvData = Dict[str, RefDict]
# {reftype: refdict}

FilterFunc = Callable[[str], bool]
# filter_func(reftype)

MatchesDict = Dict[str, List[RefSpec]]
# {reftype: [refspec, ...]}
