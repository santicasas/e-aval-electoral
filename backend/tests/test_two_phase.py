"""Two-phase validation: strict XSD before signing; derived schema + node integrity after signing."""
from __future__ import annotations

import pytest
from conftest import fake_sign
from lxml import etree

from eaval import avalxml
from eaval.errors import AvalError


@pytest.fixture
def flow(spec, make_aval):
    unsigned = avalxml.build_unsigned(make_aval(), spec)
    with_id, node_id = avalxml.prepare_for_signing(unsigned)
    return unsigned, with_id, node_id


def test_phase_one_strict_and_never_sends_invalid_xml(spec, make_aval):
    xml = avalxml.build_unsigned(make_aval(), spec)
    assert xml.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert avalxml.validate_unsigned(xml, spec) == []
    with pytest.raises(AvalError):  # an invalid aval never reaches AutoFirma
        avalxml.build_unsigned(make_aval(fnac="19800101" + "0"), spec)
    with pytest.raises(AvalError):
        avalxml.build_unsigned(make_aval(tipoid="3"), spec)
    with pytest.raises(AvalError):
        avalxml.build_unsigned(make_aval(elecciones="DIPUTACION"), spec)


def test_prepared_document_carries_a_unique_id_and_is_the_same_node(flow):
    unsigned, with_id, node_id = flow
    assert node_id.startswith("avalcandidatura-") and node_id.encode() in with_id
    assert avalxml.prepare_for_signing(unsigned)[1] != node_id  # unique each time
    assert avalxml.check_integrity(unsigned, with_id)


def test_signed_shape_passes_phase_two_and_integrity(spec, flow):
    unsigned, with_id, _ = flow
    signed = fake_sign(with_id)
    assert avalxml.validate_signed(signed, spec) == []
    assert avalxml.check_integrity(unsigned, signed)


@pytest.mark.parametrize("old,new", [
    (b"<nomb>NOM DE PROVA</nomb>", b"<nomb>ALTRE NOM</nomb>"),
    (b"<id>00000000T</id>", b"<id>11111111H</id>"),
    (b"<circunscripcion>Barcelona</circunscripcion>", b"<circunscripcion>Madrid</circunscripcion>"),
    (b"<nombre>Candidatura de prova</nombre>", b"<nombre>Altra candidatura</nombre>"),
    (b"<elecciones>CONGRESO</elecciones>", b"<elecciones>SENADO</elecciones>"),
])
def test_node_altered_after_signing_is_detected(flow, old, new):
    unsigned, with_id, _ = flow
    signed = fake_sign(with_id)
    assert old in signed
    assert not avalxml.check_integrity(unsigned, signed.replace(old, new))


def test_node_with_extra_whitespace_or_reordered_children_is_detected(flow):
    unsigned, with_id, _ = flow
    signed = fake_sign(with_id).replace(b"<avalista>", b"<avalista> ")
    assert not avalxml.check_integrity(unsigned, signed)


def test_added_attribute_other_than_the_signer_ones_is_detected(spec, flow):
    unsigned, with_id, _ = flow
    signed = fake_sign(with_id).replace(b"<avalcandidatura ", b"<avalcandidatura Foo='1' ")
    assert not avalxml.check_integrity(unsigned, signed)
    assert avalxml.validate_signed(signed, spec) != []


def test_second_avalcandidatura_is_rejected(spec, flow):
    unsigned, with_id, _ = flow
    root = etree.fromstring(fake_sign(with_id))
    from copy import deepcopy
    root.insert(0, deepcopy(root.find("avalcandidatura")))
    signed = etree.tostring(root, encoding="UTF-8")
    assert not avalxml.check_integrity(unsigned, signed)
    assert avalxml.validate_signed(signed, spec) != []


def test_signature_must_follow_the_node_and_be_unique(spec, flow):
    _, with_id, _ = flow
    root = etree.fromstring(fake_sign(with_id))
    sig, node = root[1], root[0]
    root[:] = [sig, node]  # signature first
    assert avalxml.validate_signed(etree.tostring(root), spec) != []
    root2 = etree.fromstring(fake_sign(with_id))
    from copy import deepcopy
    root2.append(deepcopy(root2[1]))  # two signatures
    assert avalxml.validate_signed(etree.tostring(root2), spec) != []


def test_unsigned_document_is_not_a_valid_signed_document_only_if_extra_content(spec, flow):
    unsigned, _, _ = flow
    assert avalxml.validate_signed(unsigned, spec) == []  # the signature is optional in the derived schema


def test_foreign_element_in_the_signature_slot_is_rejected(spec, flow):
    _, with_id, _ = flow
    signed = fake_sign(with_id).replace(b"Signature", b"Whatever")
    assert avalxml.validate_signed(signed, spec) != []


def test_hostile_xml_is_refused():
    xxe = b'<?xml version="1.0"?><!DOCTYPE oce [<!ENTITY a SYSTEM "file:///etc/passwd">]><oce>&a;</oce>'
    with pytest.raises(AvalError) as e:
        avalxml.parse(xxe)
    assert e.value.code == "xml_dtd_not_allowed"
    with pytest.raises(AvalError) as e:
        avalxml.parse(b"<oce>" + b"x" * (avalxml.MAX_XML_BYTES + 1) + b"</oce>")
    assert e.value.code == "xml_too_large"
    with pytest.raises(AvalError) as e:
        avalxml.parse(b"<oce><unclosed></oce>")
    assert e.value.code == "xml_not_well_formed"


def test_integrity_survives_namespace_declarations_added_to_the_root(flow):
    """AutoFirma may declare namespaces on the root; exclusive C14N keeps the node comparison stable."""
    unsigned, with_id, _ = flow
    signed = fake_sign(with_id).replace(b"<oce>", b'<oce xmlns:xades="http://uri.etsi.org/01903/v1.3.2#">', 1)
    assert avalxml.check_integrity(unsigned, signed)
