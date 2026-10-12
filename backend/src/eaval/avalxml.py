"""Aval XML: model, generation, preparation for signing, two-phase validation and node integrity.

Flow: ``build_unsigned`` (strictly valid against the official XSD) -> ``prepare_for_signing`` (adds the node
``Id`` that AutoFirma needs) -> AutoFirma -> ``validate_signed`` (derived schema + structural checks) ->
``check_integrity`` (the node, minus signer-added attributes, must equal the generated one).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from lxml import etree

from . import constituencies
from .errors import AvalError
from .schema import DS, SIGNER_ATTRS, Spec, load_spec

MAX_XML_BYTES = 256 * 1024
DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>'


@dataclass(frozen=True)
class Aval:
    nomb: str
    ape1: str
    ape2: str
    fnac: str  # AAAAMMDD
    tipoid: str  # "1" NIF, "2" NIE
    id: str
    elecciones: str
    circunscripcion: str
    nombre: str  # exact candidacy name


def parse(xml: bytes) -> etree._Element:
    """Safe parse: size limit, no entities, no DTD, no network."""
    if len(xml) > MAX_XML_BYTES:
        raise AvalError("xml_too_large")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
    try:
        root = etree.fromstring(xml, parser)
    except etree.XMLSyntaxError as exc:
        raise AvalError("xml_not_well_formed", detail=str(exc)) from exc
    info = root.getroottree().docinfo
    if info.internalDTD is not None or info.externalDTD is not None:
        raise AvalError("xml_dtd_not_allowed")
    return root


def build_unsigned(aval: Aval, spec: Spec | None = None) -> bytes:
    """Generate the unsigned XML and validate it strictly against the official XSD and the coherence matrix.
    Never returns an invalid document: if this raises, nothing goes to AutoFirma."""
    spec = spec or load_spec()
    constituencies.check(aval.elecciones, aval.circunscripcion, spec)
    oce = etree.Element("oce")
    node = etree.SubElement(oce, "avalcandidatura")
    avalista = etree.SubElement(node, "avalista")
    for name in ("nomb", "ape1", "ape2", "fnac", "tipoid", "id"):
        etree.SubElement(avalista, name).text = getattr(aval, name) or None
    cand = etree.SubElement(node, "candidatura")
    for name in ("elecciones", "circunscripcion", "nombre"):
        etree.SubElement(cand, name).text = getattr(aval, name)
    xml = DECLARATION + etree.tostring(oce, encoding="UTF-8")
    errors = validate_unsigned(xml, spec)
    if errors:
        raise AvalError("schema_invalid", detail="; ".join(errors))
    return xml


def validate_unsigned(xml: bytes, spec: Spec | None = None) -> list[str]:
    """Phase 1: strict validation against the official XSD. Empty list = valid."""
    spec = spec or load_spec()
    root = parse(xml)
    spec.schema.validate(root)
    return [e.message for e in spec.schema.error_log]


def prepare_for_signing(xml: bytes) -> tuple[bytes, str]:
    """Add the unique ``Id`` AutoFirma needs (``nodeToSign`` takes the value of this attribute). The result is
    deliberately NOT valid against the official XSD (it forbids attributes); integrity is checked against the
    stored strict XML instead."""
    root = parse(xml)
    node = _node(root)
    node_id = f"avalcandidatura-{uuid.uuid4()}"
    node.set("Id", node_id)
    return DECLARATION + etree.tostring(root, encoding="UTF-8"), node_id


def _node(root: etree._Element) -> etree._Element:
    if root.tag != "oce":
        raise AvalError("bad_root", detail=str(root.tag))
    nodes = root.findall("avalcandidatura")
    if len(nodes) != 1:
        raise AvalError("avalcandidatura_count", detail=str(len(nodes)))
    return nodes[0]


def validate_signed(signed: bytes, spec: Spec | None = None) -> list[str]:
    """Phase 2: derived schema plus the structural rules the schema cannot express."""
    spec = spec or load_spec()
    root = parse(signed)
    errors: list[str] = []
    children = list(root)
    names = [(etree.QName(c).namespace, etree.QName(c).localname) if isinstance(c.tag, str) else None
             for c in children]
    if names not in ([(None, "avalcandidatura")], [(None, "avalcandidatura"), (DS, "Signature")]):
        errors.append("oce must contain avalcandidatura followed by exactly one ds:Signature")
    if sum(1 for _ in root.iter(f"{{{DS}}}Signature")) > 1:
        errors.append("more than one ds:Signature")
    spec.signed_schema.validate(root)
    errors += [e.message for e in spec.signed_schema.error_log]
    return errors


def node_c14n(root: etree._Element) -> bytes:
    """Canonical form (exclusive C14N, so surrounding namespace declarations cannot interfere) of the
    avalcandidatura node without the attributes the signer adds."""
    import copy

    node = copy.deepcopy(_node(root))
    for attr in SIGNER_ATTRS:
        node.attrib.pop(attr, None)
    return etree.tostring(node, method="c14n", exclusive=True)


def check_integrity(original_unsigned: bytes, signed: bytes) -> bool:
    """True when the signed document's node equals the one generated before signing."""
    try:
        return node_c14n(parse(original_unsigned)) == node_c14n(parse(signed))
    except AvalError:
        return False


def extract(xml: bytes) -> dict[str, str]:
    """Field values of an aval (signed or not), for consistency checks."""
    node = _node(parse(xml))
    out: dict[str, str] = {}
    for name in ("nomb", "ape1", "ape2", "fnac", "tipoid", "id"):
        out[name] = node.findtext(f"avalista/{name}") or ""
    for name in ("elecciones", "circunscripcion", "nombre"):
        out[name] = node.findtext(f"candidatura/{name}") or ""
    return out
