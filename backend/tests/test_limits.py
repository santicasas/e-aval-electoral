"""Length limits of the XSD (20, 25, 9, 100) with both overflow policies. The real-world bug this guards: a
form that accepts 40 characters in the name field while the schema allows 20."""
from __future__ import annotations

import pytest

from eaval import avalxml
from eaval.config import Options
from eaval.errors import AvalError
from eaval.prepare import prepare

from conftest import NAME, TODAY

TRUNCATE = Options(overflow="truncate", name_case="as_typed")
REJECT = Options(overflow="reject", name_case="as_typed")


@pytest.mark.parametrize("field,limit", [("nomb", 20), ("ape1", 25), ("ape2", 25)])
@pytest.mark.parametrize("delta", [0, 1])
def test_name_fields_at_and_over_the_limit(make_form, spec, field, limit, delta):
    value = "A" * (limit + delta)
    form = make_form(**{field: value})
    if delta == 0:
        aval, notices = prepare(form, NAME, today=TODAY, options=TRUNCATE)
        assert getattr(aval, field) == value and not any(n.code == "truncated" for n in notices)
        assert avalxml.validate_unsigned(avalxml.build_unsigned(aval, spec), spec) == []
        prepare(form, NAME, today=TODAY, options=REJECT)  # exactly at the limit is fine under both policies
    else:
        aval, notices = prepare(form, NAME, today=TODAY, options=TRUNCATE)
        assert len(getattr(aval, field)) == limit
        truncated = [n for n in notices if n.code == "truncated"]
        assert len(truncated) == 1 and truncated[0].field == field  # never silent
        assert avalxml.validate_unsigned(avalxml.build_unsigned(aval, spec), spec) == []
        with pytest.raises(AvalError) as e:
            prepare(form, NAME, today=TODAY, options=REJECT)
        assert e.value.code == "too_long" and e.value.field == field


def test_default_policy_is_truncate_with_notice(make_form):
    aval, notices = prepare(make_form(nomb="N" * 40), NAME, today=TODAY)
    assert len(aval.nomb) == 20 and "truncated" in [n.code for n in notices]


def test_truncation_does_not_leave_a_trailing_space(make_form):
    aval, _ = prepare(make_form(nomb="A" * 19 + " B"), NAME, today=TODAY, options=TRUNCATE)
    assert aval.nomb == "A" * 19


def test_length_counts_characters_not_bytes(make_form):
    aval, notices = prepare(make_form(nomb="É" * 20), NAME, today=TODAY, options=Options(name_case="as_typed"))
    assert len(aval.nomb) == 20 and "truncated" not in [n.code for n in notices]  # 40 bytes in UTF-8


def test_upper_case_expansion_is_counted_after_conversion(make_form):
    # "ß".upper() == "SS": 11 of them become 22 characters, over the limit after normalisation
    aval, notices = prepare(make_form(nomb="ß" * 11), NAME, today=TODAY)
    assert len(aval.nomb) == 20 and "truncated" in [n.code for n in notices]


@pytest.mark.parametrize("digits", [9, 10])
def test_id_length_9_ok_10_rejected(digits):
    from eaval.normalize import normalize_id
    if digits == 9:
        assert len(normalize_id("12345678Z", None, Options())[0]) == 9
    else:
        with pytest.raises(AvalError):
            normalize_id("012345678Z", None, Options())


@pytest.mark.parametrize("length,ok", [(100, True), (101, False)])
@pytest.mark.parametrize("policy", [TRUNCATE, REJECT])
def test_candidacy_name_100_ok_101_rejected_never_truncated(make_form, length, ok, policy):
    name = "C" * length
    if ok:
        aval, _ = prepare(make_form(), name, today=TODAY, options=policy)
        assert aval.nombre == name
    else:
        with pytest.raises(AvalError) as e:  # the exact name must match XML and ZIP: no policy truncates it
            prepare(make_form(), name, today=TODAY, options=policy)
        assert e.value.code == "candidacy_name_too_long"


def test_xsd_itself_rejects_overlong_values(spec, make_aval):
    """Defence in depth: bypassing the normaliser still cannot produce an invalid document."""
    for field, bad in (("nomb", "A" * 21), ("ape1", "A" * 26), ("id", "1" * 10), ("nombre", "A" * 101)):
        with pytest.raises(AvalError) as e:
            avalxml.build_unsigned(make_aval(**{field: bad}), spec)
        assert e.value.code == "schema_invalid"
