"""Errors for R6Pugs package."""

__all__ = [
    "R6PugsError", "Forbidden", "ExtensionNotFound", "InvalidExtension",
    "ReactionMenuError", "MenuNotSent"
]


class R6PugsError(Exception):
    """Base class for this module."""

    pass


class Forbidden(R6PugsError):
    """User is not permitted to join a PuG."""

    pass


class ExtensionNotFound(R6PugsError):
    """R6Pugs extension was not found."""

    pass


class InvalidExtension(R6PugsError):
    """There was an error in the extension python."""

    pass


class ReactionMenuError(Exception):
    """Base class for ReactionMenus."""

    pass


class MenuNotSent(ReactionMenuError):
    """No message has been sent yet."""

    pass


'''Copyright (c) 2017, 2018 Tobotimus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
