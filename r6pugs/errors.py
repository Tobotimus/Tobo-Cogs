"""Errors for R6Pugs package."""

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
