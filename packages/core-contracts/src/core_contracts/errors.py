"""Domain exceptions shared across packages.

TODO: add fields (e.g. offending status, rule code) as needed.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class IllegalTransition(DomainError):
    """A recommendation status change that the state machine forbids."""


class MappingError(DomainError):
    """A client event could not be mapped to a canonical event."""


class ContextTooSmall(DomainError):
    """Not enough in-context rows for a TabPFN call; caller must fall back."""


class PolicyViolation(DomainError):
    """A hard policy rule was broken."""
