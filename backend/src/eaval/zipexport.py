"""Delivery ZIPs: one per election, constituency and candidacy, named ``EEEEEE.CCCCCC.PPPPPP.zip``, containing
one ``NIF.xml`` per aval.

Open point (BOE silent): several official values contain ``/`` (``Araba/Álava``...), which cannot be part of a
file name. ``Options.path_replacements`` is the configurable substitution (provisionally ``-``); the choice must
be confirmed with the Junta. The XML values are never altered: only the ZIP name is.
"""
from __future__ import annotations

import io
import unicodedata
import zipfile
from dataclasses import dataclass

from . import avalxml
from .config import Options
from .errors import AvalError, Notice
from .schema import Spec, load_spec

ZIP_NAME_MAX_BYTES = 255  # common file-system limit, in UTF-8 bytes
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # reproducible archives
_UTF8_FLAG = 0x800  # general-purpose bit 11: entry names are UTF-8


def safe_component(value: str, options: Options) -> tuple[str, list[Notice]]:
    """File-name-safe version of a name part, plus notices for what was substituted."""
    value = unicodedata.normalize("NFC", value)
    out, notices = [], []
    for ch in value:
        if ch in options.path_replacements:
            out.append(options.path_replacements[ch])
            notices.append(Notice("path_char_replaced", "", ch, options.path_replacements[ch]))
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            raise AvalError("control_char_in_name", "", repr(ch))
        else:
            out.append(ch)
    result = "".join(out)
    if result != result.strip() or result.endswith("."):
        raise AvalError("name_edge_not_portable", "", "leading/trailing space or trailing dot")
    if "." in result:
        # The format EEEEEE.CCCCCC.PPPPPP uses the dot as separator: ambiguous for readers. Pending the Junta.
        notices.append(Notice("dot_in_name_part", "", result, result))
    return result, notices


def zip_name(elecciones: str, circunscripcion: str, nombre: str, options: Options | None = None) -> tuple[str, list[Notice]]:
    options = options or Options()
    parts, notices = [], []
    for part in (elecciones, circunscripcion, nombre):
        safe, n = safe_component(part, options)
        parts.append(safe)
        notices += n
    name = ".".join(parts) + ".zip"
    if len(name.encode("utf-8")) > ZIP_NAME_MAX_BYTES:
        raise AvalError("zip_name_too_long", "", str(len(name.encode("utf-8"))))
    return name, notices


@dataclass(frozen=True)
class SignedAval:
    xml: bytes  # the signed XML as returned by AutoFirma
    cert_nif: str  # NIF extracted from the certificate (already validated upstream)


def build_zip(avals: list[SignedAval], elecciones: str, circunscripcion: str, nombre: str,
              options: Options | None = None, spec: Spec | None = None) -> tuple[str, bytes, list[Notice]]:
    """Return (zip file name, zip bytes, notices). Every aval must match the ZIP's election, constituency and
    candidacy name, and its ``id`` must equal the certificate NIF; otherwise AvalError."""
    spec = spec or load_spec()
    name, notices = zip_name(elecciones, circunscripcion, nombre, options)
    buffer = io.BytesIO()
    seen: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(avals, key=lambda a: a.cert_nif):
            errors = avalxml.validate_signed(item.xml, spec)
            if errors:
                raise AvalError("signed_xml_invalid", "", "; ".join(errors))
            fields = avalxml.extract(item.xml)
            for key, expected in (("elecciones", elecciones), ("circunscripcion", circunscripcion),
                                  ("nombre", nombre)):
                if fields[key] != expected:
                    raise AvalError("aval_does_not_match_zip", key, f"{fields[key]!r} != {expected!r}")
            nif = fields["id"]
            if nif != item.cert_nif.upper():
                raise AvalError("nif_mismatch_certificate", "id")
            if nif in seen:
                raise AvalError("duplicate_nif_in_zip", "id")
            seen.add(nif)
            info = zipfile.ZipInfo(f"{nif}.xml", date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= _UTF8_FLAG
            zf.writestr(info, item.xml)
    return name, buffer.getvalue(), notices
