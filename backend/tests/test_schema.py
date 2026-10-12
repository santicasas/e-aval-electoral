from __future__ import annotations

from conftest import fake_sign

from eaval import avalxml
from eaval.schema import OFFICIAL_XSD, SIGNED_XSD, SPEC_DIR, derive_signed_xsd

CALL = SPEC_DIR / "generales-2026"


def test_official_example_validates(spec):
    assert avalxml.validate_unsigned((CALL / "example-unsigned.xml").read_bytes(), spec) == []


def test_official_xsd_facts(spec):
    assert len(spec.circunscripciones) == 63 and len(set(spec.circunscripciones)) == 63
    assert spec.elecciones == ["CONGRESO", "SENADO", "CONGRESO Y SENADO", "PARLAMENTO EUROPEO"]
    assert spec.max_length("nombavalista") == 20
    assert spec.max_length("apellidoavalista") == 25
    assert spec.max_length("identificador") == 9
    assert spec.max_length("nombcandidatura") == 100


def test_element_is_circunscripcion_without_accent(spec):
    xml = (CALL / "example-unsigned.xml").read_bytes()
    assert avalxml.validate_unsigned(xml, spec) == []
    accented = xml.replace(b"circunscripcion", "circunscripción".encode())
    assert avalxml.validate_unsigned(accented, spec) != []


def test_derived_schema_is_generated_not_hand_edited():
    """The committed derived XSD must equal what the generator produces from the official one."""
    assert derive_signed_xsd((CALL / OFFICIAL_XSD).read_bytes()) == (CALL / SIGNED_XSD).read_bytes()


def test_official_schema_rejects_what_signing_adds(spec, make_aval):
    xml = avalxml.build_unsigned(make_aval(), spec)
    with_id, _ = avalxml.prepare_for_signing(xml)
    assert avalxml.validate_unsigned(with_id, spec) != []  # only the Id attribute already fails
    assert avalxml.validate_unsigned(fake_sign(with_id), spec) != []


def test_derived_schema_accepts_signed_shape_and_still_rejects_garbage(spec, make_aval):
    xml = avalxml.build_unsigned(make_aval(), spec)
    with_id, _ = avalxml.prepare_for_signing(xml)
    assert avalxml.validate_signed(fake_sign(with_id), spec) == []
    assert avalxml.validate_signed(fake_sign(with_id, extra_attrs=False), spec) == []
    bad = fake_sign(with_id).replace(b"<nomb>", b"<nomb x='1'>")
    assert avalxml.validate_signed(bad, spec) != []
    unknown_attr = fake_sign(with_id).replace(b"<avalcandidatura ", b"<avalcandidatura Foo='1' ")
    assert avalxml.validate_signed(unknown_attr, spec) != []
