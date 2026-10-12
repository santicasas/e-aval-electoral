from __future__ import annotations

import pytest

from eaval import avalxml
from eaval import constituencies as c
from eaval.errors import AvalError

ALL_ELECTIONS = [c.CONGRESO, c.SENADO, c.AMBOS, c.EUROPEO]


def test_matrix_sizes(spec):
    assert len(c.allowed(c.CONGRESO, spec)) == 52  # 50 provinces + Ceuta + Melilla
    assert len(c.allowed(c.SENADO, spec)) == 59  # 49 non-insular + 10 islands
    assert len(c.allowed(c.AMBOS, spec)) == 49
    assert c.allowed(c.EUROPEO, spec) == [c.NACIONAL]


def test_every_official_value_is_reachable_and_generates_valid_xml(spec, make_aval):
    reached = set()
    for elecciones in ALL_ELECTIONS:
        for circ in c.allowed(elecciones, spec):
            xml = avalxml.build_unsigned(make_aval(elecciones=elecciones, circunscripcion=circ), spec)
            assert avalxml.validate_unsigned(xml, spec) == []
            reached.add(circ)
    assert reached == set(spec.circunscripciones)  # all 63 official values are usable


@pytest.mark.parametrize("bad", ["Ibiza", "Formentera", "Ibiza Formentera", "ibiza-formentera", "Barcelona ",
                                 "Araba", "Alava", "Valencia", "", "Coruña"])
def test_values_outside_the_list_fail_both_in_code_and_in_the_xsd(spec, make_aval, bad):
    with pytest.raises(AvalError) as e:
        avalxml.build_unsigned(make_aval(circunscripcion=bad), spec)
    assert e.value.code == "unknown_constituency"
    raw = avalxml.DECLARATION + (
        "<oce><avalcandidatura><avalista><nomb>A</nomb><ape1>B</ape1><ape2/><fnac>19800101</fnac>"
        "<tipoid>1</tipoid><id>00000000T</id></avalista><candidatura><elecciones>CONGRESO</elecciones>"
        f"<circunscripcion>{bad}</circunscripcion><nombre>X</nombre></candidatura></avalcandidatura></oce>"
    ).encode()
    assert avalxml.validate_unsigned(raw, spec) != []


@pytest.mark.parametrize("insular", list(c.INSULAR))
def test_both_chambers_not_valid_in_insular_provinces(spec, insular):
    with pytest.raises(AvalError) as e:
        c.check(c.AMBOS, insular, spec)
    assert e.value.code == "both_chambers_insular"


@pytest.mark.parametrize("island", list(c.ISLANDS))
def test_islands_only_with_senado(spec, island):
    c.check(c.SENADO, island, spec)
    for other in (c.CONGRESO, c.AMBOS, c.EUROPEO):
        with pytest.raises(AvalError):
            c.check(other, island, spec)


@pytest.mark.parametrize("insular", list(c.INSULAR))
def test_senado_needs_the_island_not_the_province(spec, insular):
    c.check(c.CONGRESO, insular, spec)
    with pytest.raises(AvalError):
        c.check(c.SENADO, insular, spec)


def test_national_constituency_only_with_europeo(spec):
    c.check(c.EUROPEO, c.NACIONAL, spec)
    for elecciones in (c.CONGRESO, c.SENADO, c.AMBOS):
        with pytest.raises(AvalError):
            c.check(elecciones, c.NACIONAL, spec)
    with pytest.raises(AvalError):
        c.check(c.EUROPEO, "Barcelona", spec)


def test_islands_belong_to_the_right_province():
    assert c.ISLANDS["Fuerteventura"] == "Palmas, Las" and c.ISLANDS["La Gomera"] == "Santa Cruz de Tenerife"
    assert c.ISLANDS["Menorca"] == "Balears, Illes"
    assert len(c.ISLANDS) == 10


def test_required_avals_non_insular_is_a_single_aval(spec):
    assert c.required_avals(c.AMBOS, "Almería", spec=spec) == [c.AvalSlot(c.AMBOS, "Almería")]
    assert c.required_avals(c.AMBOS, "Ceuta", spec=spec) == [c.AvalSlot(c.AMBOS, "Ceuta")]


def test_required_avals_insular_both_chambers_needs_two_avals(spec):
    assert c.required_avals(c.AMBOS, "Balears, Illes", "Menorca", spec=spec) == [
        c.AvalSlot(c.CONGRESO, "Balears, Illes"), c.AvalSlot(c.SENADO, "Menorca")]
    assert c.required_avals(c.AMBOS, "Santa Cruz de Tenerife", "La Palma", spec=spec)[1] == c.AvalSlot(
        c.SENADO, "La Palma")


def test_required_avals_insular_single_chamber(spec):
    assert c.required_avals(c.CONGRESO, "Palmas, Las", spec=spec) == [c.AvalSlot(c.CONGRESO, "Palmas, Las")]
    assert c.required_avals(c.SENADO, "Palmas, Las", "Lanzarote", spec=spec) == [c.AvalSlot(c.SENADO, "Lanzarote")]


def test_required_avals_errors(spec):
    with pytest.raises(AvalError) as e:
        c.required_avals(c.AMBOS, "Balears, Illes", spec=spec)
    assert e.value.code == "island_required"
    with pytest.raises(AvalError) as e:
        c.required_avals(c.AMBOS, "Balears, Illes", "Tenerife", spec=spec)
    assert e.value.code == "island_not_in_province"
    with pytest.raises(AvalError):
        c.required_avals(c.AMBOS, "Madrid", "Mallorca", spec=spec)
    assert c.required_avals(c.EUROPEO, "Madrid", spec=spec) == [c.AvalSlot(c.EUROPEO, c.NACIONAL)]
