"""Errors for the docref package."""

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
