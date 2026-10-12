"""Delivery ZIPs: names (accents, spaces, '/'), contents and consistency checks."""
from __future__ import annotations

import os
import unicodedata
import zipfile
from io import BytesIO

import pytest
from conftest import NAME, fake_sign

from eaval import avalxml
from eaval.config import Options
from eaval.errors import AvalError
from eaval.zipexport import SignedAval, build_zip, safe_component, zip_name


def signed_aval(make_aval, nif="00000000T", **kw):
    aval = make_aval(id=nif, **kw)
    with_id, _ = avalxml.prepare_for_signing(avalxml.build_unsigned(aval))
    return SignedAval(xml=fake_sign(with_id), cert_nif=nif)


def test_example_name_from_the_instruction():
    name, notices = zip_name("CONGRESO Y SENADO", "Almería", "Candidatura1")
    assert name == "CONGRESO Y SENADO.Almería.Candidatura1.zip" and notices == []


@pytest.mark.parametrize("value,expected", [
    ("Araba/Álava", "Araba-Álava"),
    ("Alicante/Alacant", "Alicante-Alacant"),
    ("Castellón/Castelló", "Castellón-Castelló"),
    ("Valencia/València", "Valencia-València"),
])
def test_slash_values_get_the_configured_replacement(value, expected):
    name, notices = zip_name("CONGRESO", value, "X")
    assert name == f"CONGRESO.{expected}.X.zip"
    assert [n.code for n in notices] == ["path_char_replaced"]


def test_replacement_character_is_configurable():
    opts = Options(path_replacements={"/": "_"})
    assert zip_name("CONGRESO", "Araba/Álava", "X", opts)[0] == "CONGRESO.Araba_Álava.X.zip"


def test_every_official_slash_value_is_covered(spec):
    slashed = [c for c in spec.circunscripciones if "/" in c]
    assert sorted(slashed) == ["Alicante/Alacant", "Araba/Álava", "Castellón/Castelló", "Valencia/València"]
    for c in slashed:
        assert "/" not in zip_name("CONGRESO", c, "X")[0]


@pytest.mark.parametrize("bad", ['A:B', 'A*B', 'A?B', 'A"B', 'A<B', 'A>B', 'A|B', 'A\\B'])
def test_other_forbidden_characters_in_the_candidacy_name_are_replaced(bad):
    name, notices = zip_name("CONGRESO", "Madrid", bad)
    assert not any(ch in name for ch in ':*?"<>|\\/')
    assert notices


def test_portability_problems_are_errors_not_silent_changes():
    for bad in ("name ", " name", "name."):
        with pytest.raises(AvalError):
            safe_component(bad, Options())
    with pytest.raises(AvalError):
        safe_component("na\x00me", Options())


def test_dot_inside_a_name_part_is_flagged_because_the_format_uses_dots_as_separators():
    name, notices = zip_name("CONGRESO", "Madrid", "Uni. Popular")
    assert name == "CONGRESO.Madrid.Uni. Popular.zip" and [n.code for n in notices] == ["dot_in_name_part"]


def test_name_is_nfc_even_if_input_is_nfd():
    nfd = unicodedata.normalize("NFD", "Almería")
    name, _ = zip_name("CONGRESO", nfd, "X")
    assert name == unicodedata.normalize("NFC", name) and "Almería" in name


def test_too_long_name_is_rejected():
    with pytest.raises(AvalError) as e:
        zip_name("CONGRESO Y SENADO", "Santa Cruz de Tenerife", "é" * 100 + "ñ" * 100)
    assert e.value.code == "zip_name_too_long"


def test_zip_contents_and_entry_flags(make_aval):
    a = signed_aval(make_aval, "00000000T")
    b = signed_aval(make_aval, "12345678Z")
    name, data, _ = build_zip([b, a], "CONGRESO", "Barcelona", NAME)
    assert name == f"CONGRESO.Barcelona.{NAME}.zip"
    with zipfile.ZipFile(BytesIO(data)) as zf:
        assert zf.namelist() == ["00000000T.xml", "12345678Z.xml"]  # one NIF.xml per aval, stable order
        assert all(i.filename.isascii() for i in zf.infolist())  # entry names are ASCII: no encoding ambiguity
        assert zf.read("00000000T.xml") == a.xml
        assert zf.testzip() is None


def test_zip_is_reproducible(make_aval):
    a = signed_aval(make_aval)
    assert build_zip([a], "CONGRESO", "Barcelona", NAME)[1] == build_zip([a], "CONGRESO", "Barcelona", NAME)[1]


@pytest.mark.parametrize("zip_args", [
    ("SENADO", "Barcelona", NAME),            # election differs from the XML
    ("CONGRESO", "Madrid", NAME),             # constituency differs
    ("CONGRESO", "Barcelona", "Altra"),       # candidacy name differs
])
def test_every_xml_must_match_the_zip_name(make_aval, zip_args):
    with pytest.raises(AvalError) as e:
        build_zip([signed_aval(make_aval)], *zip_args)
    assert e.value.code == "aval_does_not_match_zip"


def test_certificate_nif_must_equal_the_id_field(make_aval):
    a = signed_aval(make_aval, "00000000T")
    wrong = SignedAval(xml=a.xml, cert_nif="12345678Z")
    with pytest.raises(AvalError) as e:
        build_zip([wrong], "CONGRESO", "Barcelona", NAME)
    assert e.value.code == "nif_mismatch_certificate"
    SignedAval(xml=a.xml, cert_nif="00000000t")  # comparison is case-insensitive
    build_zip([SignedAval(xml=a.xml, cert_nif="00000000t")], "CONGRESO", "Barcelona", NAME)


def test_duplicate_nif_in_one_zip_is_rejected(make_aval):
    a = signed_aval(make_aval)
    with pytest.raises(AvalError) as e:
        build_zip([a, a], "CONGRESO", "Barcelona", NAME)
    assert e.value.code == "duplicate_nif_in_zip"


def test_invalid_signed_xml_is_rejected(make_aval):
    a = signed_aval(make_aval)
    bad = SignedAval(xml=a.xml.replace(b"<nomb>", b"<nomb z='1'>"), cert_nif=a.cert_nif)
    with pytest.raises(AvalError) as e:
        build_zip([bad], "CONGRESO", "Barcelona", NAME)
    assert e.value.code == "signed_xml_invalid"


def test_island_province_needs_two_zips(make_aval):
    """The Senado aval uses the island, the Congreso one the province: two ZIPs, same NIF.xml in each."""
    congreso = signed_aval(make_aval, elecciones="CONGRESO", circunscripcion="Balears, Illes")
    senado = signed_aval(make_aval, elecciones="SENADO", circunscripcion="Menorca")
    n1, d1, _ = build_zip([congreso], "CONGRESO", "Balears, Illes", NAME)
    n2, d2, _ = build_zip([senado], "SENADO", "Menorca", NAME)
    assert n1 != n2 and n1.startswith("CONGRESO.Balears, Illes.") and n2.startswith("SENADO.Menorca.")
    with pytest.raises(AvalError):  # an island aval cannot go in the province ZIP
        build_zip([senado], "CONGRESO", "Balears, Illes", NAME)


def test_zip_file_with_accents_and_spaces_survives_the_file_system(make_aval, tmp_path):
    """Written and listed back on this OS (Windows/macOS/Linux): the name stays NFC with accents and spaces."""
    a = signed_aval(make_aval, elecciones="CONGRESO Y SENADO", circunscripcion="Almería", nombre="Candidatura1")
    name, data, _ = build_zip([a], "CONGRESO Y SENADO", "Almería", "Candidatura1")
    (tmp_path / name).write_bytes(data)
    listed = [unicodedata.normalize("NFC", n) for n in os.listdir(tmp_path)]
    assert listed == ["CONGRESO Y SENADO.Almería.Candidatura1.zip"]
    with zipfile.ZipFile(tmp_path / name) as zf:
        assert zf.namelist() == ["00000000T.xml"]
