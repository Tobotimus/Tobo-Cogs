"""Errors for R6Pugs package."""

class R6PugsError(Exception):
    """Base class for this module."""
    pass

class Forbidden(R6PugsError):
    """User is not permitted to join a PuG."""
    pass
