"""PoC: aval XML generation, node integrity check and schema validation.

Throwaway code (Phase 0). Not part of the platform.
"""
from __future__ import annotations

import copy

from pathlib import Path

from lxml import etree

DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
# Attributes the AutoFirma XAdES signer adds to the signed node (see BOE example, image 14814_006).
SIGNER_ADDED_ATTRS = ("Id", "MimeType", "Encoding")
XSD_PATH = Path(__file__).resolve().parent.parent / "spec-draft" / "oce.UNVERIFIED.xsd"

FIELDS_AVALISTA = ("nomb", "ape1", "ape2", "fnac", "tipoid", "id")
FIELDS_CANDIDATURA = ("elecciones", "circunscripción", "nombre")


def build_unsigned(data: dict, node_id: str | None = None) -> bytes:
    """Build the unsigned aval document: <oce><avalcandidatura>...</avalcandidatura></oce>."""
    oce = etree.Element("oce")
    node = etree.SubElement(oce, "avalcandidatura")
    if node_id:
        node.set("Id", node_id)
    avalista = etree.SubElement(node, "avalista")
    for name in FIELDS_AVALISTA:
        etree.SubElement(avalista, name).text = data[name]
    candidatura = etree.SubElement(node, "candidatura")
    for name in FIELDS_CANDIDATURA:
        etree.SubElement(candidatura, name).text = data[name]
    return etree.tostring(oce, xml_declaration=True, encoding="UTF-8", standalone=None)


def _find_node(root: etree._Element) -> etree._Element:
    nodes = root.findall("avalcandidatura")
    if len(nodes) != 1:
        raise ValueError(f"expected exactly one avalcandidatura under the root, found {len(nodes)}")
    return nodes[0]


def normalized_node_c14n(xml: bytes) -> bytes:
    """C14N of avalcandidatura with signer-added attributes removed and Signature siblings ignored."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(xml, parser)
    node = copy.deepcopy(_find_node(root))
    for attr in SIGNER_ADDED_ATTRS:
        node.attrib.pop(attr, None)
    return etree.tostring(node, method="c14n")


def integrity_ok(original: bytes, signed: bytes) -> tuple[bool, str]:
    try:
        a = normalized_node_c14n(original)
        b = normalized_node_c14n(signed)
    except Exception as exc:  # noqa: BLE001 - PoC report
        return False, f"error: {exc}"
    return (a == b, "identical" if a == b else "node differs from the generated one")


def schema_validate(xml: bytes) -> tuple[bool, list[str]]:
    """Validate the unsigned structure: strip ds:Signature and signer-added attributes first."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(xml, parser)
    for sig in root.findall(f"{{{DSIG_NS}}}Signature"):
        root.remove(sig)
    node = _find_node(root)
    for attr in SIGNER_ADDED_ATTRS:
        node.attrib.pop(attr, None)
    schema = etree.XMLSchema(etree.parse(str(XSD_PATH)))
    ok = schema.validate(root)
    return ok, [str(e) for e in schema.error_log]
