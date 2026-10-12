"""Loading of the official XSD (one directory per election call under ``spec/``) and derivation of the
post-signature schema.

The signed aval does not validate against the official XSD: the signer adds ``Id``/``Encoding``/``MimeType``
attributes to ``avalcandidatura`` and a ``ds:Signature`` inside ``oce``. The derived schema adds exactly those,
generated from the official file (never edited by hand): see ``derive_signed_xsd``.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

XS = "http://www.w3.org/2001/XMLSchema"
DS = "http://www.w3.org/2000/09/xmldsig#"
SPEC_DIR = Path(__file__).resolve().parents[3] / "spec"
OFFICIAL_XSD = "aval-jec-2011.xsd"
SIGNED_XSD = "aval-jec-2011.signed.xsd"
DEFAULT_CALL = "generales-2026"
SIGNER_ATTRS = ("Id", "Encoding", "MimeType")

_HEADER = """GENERATED FILE - DO NOT EDIT.
  Derived from {official} by eaval.schema.derive_signed_xsd (run: python -m eaval.schema).
  Adds to the official schema only what a signed aval contains and the official XSD forbids:
    - optional attributes Id, Encoding and MimeType on avalcandidatura (added by the signer);
    - one optional ds:Signature after avalcandidatura inside oce (checked further in code).
  Use the official schema for the unsigned document, this one for the signed document."""


def derive_signed_xsd(official: bytes) -> bytes:
    root = etree.fromstring(official)
    q = lambda name: f"{{{XS}}}{name}"  # noqa: E731
    seq = root.find(f"{q('element')}[@name='oce']/{q('complexType')}/{q('sequence')}")
    etree.SubElement(seq, q("any"), namespace=DS, processContents="lax", minOccurs="0", maxOccurs="1")
    ctype = root.find(f"{q('complexType')}[@name='avalcandidaturaType']")
    for name in SIGNER_ATTRS:
        etree.SubElement(ctype, q("attribute"), name=name, type="xs:string", use="optional")
    root.addprevious(etree.Comment(_HEADER.format(official=OFFICIAL_XSD)))
    return etree.tostring(root.getroottree(), xml_declaration=True, encoding="UTF-8", pretty_print=True)


@dataclass(frozen=True)
class Spec:
    call: str
    official: etree._ElementTree
    schema: etree.XMLSchema
    signed_schema: etree.XMLSchema

    def enumeration(self, type_name: str) -> list[str]:
        """Enumeration values of a simpleType, in schema order."""
        path = f".//{{{XS}}}simpleType[@name='{type_name}']//{{{XS}}}enumeration"
        return [e.get("value") for e in self.official.getroot().iterfind(path)]

    def max_length(self, type_name: str) -> int:
        path = f".//{{{XS}}}simpleType[@name='{type_name}']//{{{XS}}}maxLength"
        return int(self.official.getroot().find(path).get("value"))

    @property
    def elecciones(self) -> list[str]:
        return self.enumeration("tipoelecciones")

    @property
    def circunscripciones(self) -> list[str]:
        return self.enumeration("circunscripcionINE")


@functools.lru_cache(maxsize=None)
def load_spec(call: str = DEFAULT_CALL) -> Spec:
    directory = SPEC_DIR / call
    official = etree.parse(str(directory / OFFICIAL_XSD))
    signed = etree.parse(str(directory / SIGNED_XSD))
    return Spec(call, official, etree.XMLSchema(official), etree.XMLSchema(signed))


def write_derived(call: str = DEFAULT_CALL) -> Path:
    directory = SPEC_DIR / call
    out = directory / SIGNED_XSD
    out.write_bytes(derive_signed_xsd((directory / OFFICIAL_XSD).read_bytes()))
    return out


if __name__ == "__main__":
    print("wrote", write_derived())
