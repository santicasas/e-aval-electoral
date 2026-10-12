from __future__ import annotations

from datetime import date

import pytest

from eaval.config import Options
from eaval.errors import AvalError
from eaval.normalize import (NIF_LETTERS, age_on, clean_text, normalize_id, normalize_name, parse_birth_date,
                             upper_ascii_keep_nc)
from eaval.prepare import prepare

from conftest import ELECTION, NAME, TODAY

OPT = Options()


# ---- text cleaning ---------------------------------------------------------------------------------------------

def test_clean_text_whitespace_and_invisible_characters():
    assert clean_text("  Maria   del Mar \t") == "Maria del Mar"
    assert clean_text("Jo​sep‍") == "Josep"  # zero-width space / joiner
    assert clean_text("Anna‮") == "Anna"  # bidi override
    assert clean_text("Pau­la") == "Paula"  # soft hyphen
    assert clean_text("A\x00B\x07C") == "ABC"  # control characters
    assert clean_text("Rosa\nMaria") == "Rosa Maria"


def test_clean_text_normalises_to_nfc():
    decomposed = "José"  # e + combining acute
    assert clean_text(decomposed) == "José" and len(clean_text(decomposed)) == 4


def test_upper_ascii_strips_accents_but_keeps_n_tilde_and_c_cedilla():
    assert upper_ascii_keep_nc("José Ñandú Çelik") == "JOSE ÑANDU ÇELIK"
    assert upper_ascii_keep_nc("Àngels Núñez-Pérez") == "ANGELS NÚÑEZ-PEREZ".replace("Ú", "U")
    assert upper_ascii_keep_nc("Müller") == "MULLER"
    assert upper_ascii_keep_nc("Garçon") == "GARÇON"


def test_name_policy_as_typed_keeps_everything():
    opts = Options(name_case="as_typed")
    value, notices = normalize_name("nomb", "José", 20, opts, required=True)
    assert value == "José" and notices == []


def test_name_policy_upper_ascii_reports_the_change():
    value, notices = normalize_name("nomb", "José", 20, OPT, required=True)
    assert value == "JOSE"
    assert [n.code for n in notices] == ["case_or_accents_changed"]


def test_second_surname_may_be_empty_but_name_and_first_surname_may_not():
    assert normalize_name("ape2", "   ", 25, OPT, required=False)[0] == ""
    for field in ("nomb", "ape1"):
        with pytest.raises(AvalError) as e:
            normalize_name(field, " ​ ", 20, OPT, required=True)
        assert e.value.code == "required"


def test_empty_second_surname_generates_a_valid_xml(spec, make_aval):
    from eaval import avalxml
    xml = avalxml.build_unsigned(make_aval(ape2=""), spec)
    assert b"<ape2/>" in xml and avalxml.validate_unsigned(xml, spec) == []


# ---- NIF / NIE -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("00000000T", "00000000T"),
    ("12345678Z", "12345678Z"),
    ("12.345.678-z", "12345678Z"),
    (" 12345678 z ", "12345678Z"),
    ("1234567L", "01234567L"),  # 7 digits -> left-padded with zeros
    ("234567J", "00234567J"),   # 6 digits (234567 % 23 == 13 -> J)
])
def test_dni_normalisation_and_zero_padding(raw, expected):
    assert normalize_id(raw, "1", OPT) == (expected, "1")


def test_control_letter_arithmetic_matches_the_official_table():
    assert NIF_LETTERS[0] == "T" and NIF_LETTERS[14] == "Z" and NIF_LETTERS[22] == "E"
    assert 12345678 % 23 == 14 and 1234567 % 23 == 19 and NIF_LETTERS[19] == "L"


@pytest.mark.parametrize("raw,expected", [("X1234567L", "X1234567L"), ("y1234567x", "Y1234567X"),
                                           ("Z1234567R", "Z1234567R")])
def test_nie_normalisation(raw, expected):
    assert normalize_id(raw, "2", OPT) == (expected, "2")


@pytest.mark.parametrize("bad,code", [
    ("12345678A", "invalid_id_letter"),
    ("00000000A", "invalid_id_letter"),
    ("X1234567A", "invalid_id_letter"),
    ("123456789", "invalid_id_format"),
    ("1234567890T", "invalid_id_format"),
    ("ABCDEFGHI", "invalid_id_format"),
    ("", "required"),
    ("K1234567L", "special_nif_not_accepted"),
    ("L1234567L", "special_nif_not_accepted"),
    ("M1234567L", "special_nif_not_accepted"),
])
def test_invalid_ids(bad, code):
    with pytest.raises(AvalError) as e:
        normalize_id(bad, None, OPT)
    assert e.value.code == code


def test_tipoid_must_agree_with_the_id():
    with pytest.raises(AvalError) as e:
        normalize_id("X1234567L", "1", OPT)
    assert e.value.code == "tipoid_mismatch"
    with pytest.raises(AvalError):
        normalize_id("12345678Z", "2", OPT)
    assert normalize_id("12345678Z", None, OPT)[1] == "1"


def test_special_nifs_can_be_allowed_by_option():
    with pytest.raises(AvalError) as e:  # still fails: K/L/M have no standard control letter rule here
        normalize_id("K1234567L", None, Options(reject_special_nif=False))
    assert e.value.code == "invalid_id_format"


# ---- dates -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["1980-01-01", "01/01/1980", "01-01-1980", "19800101", date(1980, 1, 1)])
def test_birth_date_formats(raw):
    assert parse_birth_date(raw, today=TODAY) == date(1980, 1, 1)


@pytest.mark.parametrize("raw,code", [("2026-10-13", "birth_date_in_future"), ("2030-01-01", "birth_date_in_future"),
                                      ("1899-12-31", "birth_date_implausible"), ("31/02/1990", "invalid_date"),
                                      ("1990-13-01", "invalid_date"), ("hola", "invalid_date"), ("", "invalid_date")])
def test_invalid_birth_dates(raw, code):
    with pytest.raises(AvalError) as e:
        parse_birth_date(raw, today=TODAY)
    assert e.value.code == code


def test_today_is_not_in_the_future():
    assert parse_birth_date("2026-10-12", today=TODAY) == TODAY


def test_age_on_election_day_boundary(make_form):
    assert age_on(date(2008, 11, 29), ELECTION) == 18
    assert age_on(date(2008, 11, 30), ELECTION) == 17
    prepare(make_form(fnac="2008-11-29"), NAME, today=TODAY, election_date=ELECTION)  # 18 on election day
    with pytest.raises(AvalError) as e:
        prepare(make_form(fnac="2008-11-30"), NAME, today=TODAY, election_date=ELECTION)
    assert e.value.code == "underage_on_election_day"
    prepare(make_form(fnac="2008-11-30"), NAME, today=TODAY, election_date=ELECTION,
            options=Options(enforce_min_age=False))


# ---- end to end preparation -----------------------------------------------------------------------------------

def test_prepare_returns_normalised_aval_and_notices(make_form):
    aval, notices = prepare(make_form(nomb=" josé  ", ape1="Ñandú", ape2="", id="1234567l", fnac="01/01/1980"),
                            "  Candidatura de prova ", today=TODAY, election_date=ELECTION)
    assert (aval.nomb, aval.ape1, aval.ape2, aval.id, aval.fnac, aval.tipoid) == (
        "JOSE", "ÑANDU", "", "01234567L", "19800101", "1")
    assert aval.nombre == NAME
    assert {n.code for n in notices} >= {"whitespace_cleaned", "case_or_accents_changed", "id_normalised"}


def test_nie_is_not_allowed_for_general_elections(make_form):
    with pytest.raises(AvalError) as e:
        prepare(make_form(id="X1234567L"), NAME, today=TODAY)
    assert e.value.code == "nie_not_allowed_for_general_elections"
    prepare(make_form(id="X1234567L", elecciones="PARLAMENTO EUROPEO", circunscripcion="Circunscripción Nacional"),
            NAME, today=TODAY)


def test_prepare_rejects_incoherent_constituency(make_form):
    with pytest.raises(AvalError) as e:
        prepare(make_form(elecciones="CONGRESO Y SENADO", circunscripcion="Balears, Illes"), NAME, today=TODAY)
    assert e.value.code == "both_chambers_insular"
