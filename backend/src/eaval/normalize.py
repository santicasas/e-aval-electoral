"""Normalisation of the signer's data. Anything that changes what the user typed is reported as a Notice
that the UI must show before signing; nothing is truncated or altered silently."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from .config import Options
from .errors import AvalError, Notice

NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_ID_NOISE = re.compile(r"[\s\-\. ‐-―]")
_DNI = re.compile(r"^(\d{1,8})([A-Z])$")
_NIE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_SPECIAL = re.compile(r"^[KLM]")


def clean_text(value: str) -> str:
    """NFC, invisible characters removed, any whitespace run collapsed to one space, trimmed."""
    value = unicodedata.normalize("NFC", value)
    out = []
    for ch in value:
        cat = unicodedata.category(ch)
        if cat == "Zs" or ch in "\t\n\r\x0b\x0c":
            out.append(" ")
        elif cat in ("Cf", "Cc", "Zl", "Zp", "Cs"):
            continue  # zero-width spaces/joiners, bidi marks, soft hyphen, other control characters
        else:
            out.append(ch)
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def upper_ascii_keep_nc(value: str) -> str:
    """Upper case and strip accents, keeping Ñ and Ç."""
    out = []
    for ch in unicodedata.normalize("NFC", value).upper():
        if ch in "ÑÇ":
            out.append(ch)
        else:
            out.append("".join(c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn"))
    return unicodedata.normalize("NFC", "".join(out))


def normalize_name(field: str, raw: str, max_len: int, options: Options, *, required: bool) -> tuple[str, list[Notice]]:
    notices: list[Notice] = []
    value = clean_text(raw)
    if value != raw:
        notices.append(Notice("whitespace_cleaned", field, raw, value))
    if options.name_case == "upper_ascii":
        converted = upper_ascii_keep_nc(value)
        if converted != value:
            notices.append(Notice("case_or_accents_changed", field, value, converted))
        value = converted
        if any(ord(c) > 127 and c not in "ÑÇ" for c in value):
            notices.append(Notice("non_latin_characters_kept", field, value, value))
    if required and not value:
        raise AvalError("required", field)
    if len(value) > max_len:
        if options.overflow == "reject":
            raise AvalError("too_long", field, f"{len(value)} > {max_len}")
        truncated = value[:max_len].rstrip()
        notices.append(Notice("truncated", field, value, truncated))
        value = truncated
    return value, notices


def _nif_letter(number: int) -> str:
    return NIF_LETTERS[number % 23]


def normalize_id(raw: str, tipoid: str | None, options: Options) -> tuple[str, str]:
    """Return (id, tipoid). tipoid "1" is a NIF (DNI), "2" a NIE. DNI numbers shorter than 8 digits are
    left-padded with zeros. The control letter is verified."""
    value = _ID_NOISE.sub("", raw).upper()
    if not value:
        raise AvalError("required", "id")
    if options.reject_special_nif and _SPECIAL.match(value):
        raise AvalError("special_nif_not_accepted", "id")
    m = _NIE.match(value)
    if m:
        detected, number = "2", int(str("XYZ".index(m.group(1))) + m.group(2))
        letter = m.group(3)
        normalized = value
    else:
        m = _DNI.match(value)
        if not m:
            raise AvalError("invalid_id_format", "id")
        detected, number, letter = "1", int(m.group(1)), m.group(2)
        normalized = m.group(1).zfill(8) + letter
    if _nif_letter(number) != letter:
        raise AvalError("invalid_id_letter", "id")
    if tipoid is not None and tipoid != detected:
        raise AvalError("tipoid_mismatch", "tipoid", f"given {tipoid}, id looks like {detected}")
    return normalized, detected


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d")


def parse_birth_date(value: str | date, *, today: date) -> date:
    if isinstance(value, date):
        parsed = value
    else:
        parsed = None
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(clean_text(value), fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            raise AvalError("invalid_date", "fnac", str(value))
    if parsed > today:
        raise AvalError("birth_date_in_future", "fnac")
    if parsed.year < 1900:
        raise AvalError("birth_date_implausible", "fnac")
    return parsed


def age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def check_min_age(birth: date, election_date: date | None, options: Options) -> None:
    if options.enforce_min_age and election_date is not None and age_on(birth, election_date) < options.min_age:
        raise AvalError("underage_on_election_day", "fnac")
