"""Configurable options. Defaults are the owner's "recommended defaults" of 2026-10-12 (docs/adr/0010) and some
are pending confirmation with the Junta Electoral: they are options, not hard-coded behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

# Characters that cannot appear in a file name on at least one of Windows, macOS, Linux. The BOE does not say
# how to write values such as "Araba/Álava" in a ZIP name: "-" is a provisional choice, pending the Junta.
DEFAULT_PATH_REPLACEMENTS: Mapping[str, str] = {
    "/": "-", "\\": "-", ":": "-", "*": "-", "?": "-", '"': "-", "<": "-", ">": "-", "|": "-",
}


@dataclass(frozen=True)
class Options:
    # "upper_ascii": upper case, accents removed except Ñ and Ç (as other platforms do); "as_typed": untouched.
    name_case: Literal["upper_ascii", "as_typed"] = "upper_ascii"
    # What to do when name/surnames exceed the XSD limit. Never truncate silently: truncation always yields a
    # Notice that the UI must show before signing.
    overflow: Literal["truncate", "reject"] = "truncate"
    # The signer must be of voting age on election day (needs ``election_date`` when preparing an aval).
    enforce_min_age: bool = True
    min_age: int = 18
    # NIF types K, L, M (minors / foreigners without NIE) cannot belong to voters.
    reject_special_nif: bool = True
    path_replacements: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_PATH_REPLACEMENTS))
