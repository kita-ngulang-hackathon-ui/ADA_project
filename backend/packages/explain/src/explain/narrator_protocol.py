"""Interface the worker's LLM client implements. Keeps HTTP out of L1."""
from typing import Protocol


class Narrator(Protocol):
    def narrate(self, system: str, user: str) -> str: ...
