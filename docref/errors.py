"""Errors for the docref package."""
from typing import Any

__all__ = (
    "DocRefException",
    "AlreadyUpToDate",
    "InvNotAvailable",
    "NoMoreRefs",
    "Forbidden",
    "InternalError",
    "HTTPError",
    "NotFound",
)


class DocRefException(Exception):
    """Base exception for this package."""


class AlreadyUpToDate(DocRefException):
    """Tried to update inventory but we already have the latest version."""


class InvNotAvailable(DocRefException):
    """Inventory is not available in the current scope, or it isn't installed."""


class NoMoreRefs(DocRefException):
    """Inventory no longer has any references, and can be un-cached."""


class Forbidden(DocRefException):
    """The user tried to do something they're not allowed to do."""


class InternalError(DocRefException):
    """An internal error occurred.

    This is most likely due to a bug or data corruption.
    """


class HTTPError(DocRefException):
    """An error occurred during a HTTP request.

    Attributes
    ----------
    code : int
        The HTTP response code.

    """

    def __init__(self, code: int, *args: Any):
        self.code = code
        super().__init__(*args)


class NotFound(HTTPError):
    """The resource was not found."""
