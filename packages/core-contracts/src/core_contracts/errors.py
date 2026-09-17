"""Domain exceptions shared across packages."""


class DomainError(Exception):
    """Base class for all domain errors."""


class IllegalTransition(DomainError):
    """A recommendation status change that the state machine forbids."""


class MappingError(DomainError):
    """A client event could not be mapped to a canonical event."""


class ContextTooSmall(DomainError):
    """Not enough in-context rows for a TabPFN call; caller must fall back."""


class CrossTenantContext(DomainError):
    """In-context rows from more than one tenant (no cross-client sharing, §4)."""


class PolicyViolation(DomainError):
    """A hard policy rule was broken."""


class NarrationRejected(DomainError, ValueError):
    """An LLM narration contains information that is not in the fact sheet."""
