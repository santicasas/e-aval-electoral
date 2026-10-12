"""Errors and notices. Every user-visible problem has a stable machine code so the UI can translate it."""
from __future__ import annotations

from dataclasses import dataclass


class AvalError(ValueError):
    """A validation failure. ``code`` is stable and translatable; ``field`` names the offending field."""

    def __init__(self, code: str, field: str = "", detail: str = ""):
        super().__init__(f"{code}" + (f" [{field}]" if field else "") + (f": {detail}" if detail else ""))
        self.code = code
        self.field = field
        self.detail = detail


@dataclass(frozen=True)
class Notice:
    """Something the signer must see BEFORE signing (e.g. a value was truncated or normalised)."""

    code: str
    field: str = ""
    before: str = ""
    after: str = ""
