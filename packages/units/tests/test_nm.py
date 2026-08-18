import pytest
from hypothesis import given, strategies as st

from units import (
    NM_PER_FOOT,
    NM_PER_INCH,
    ParseError,
    format_feet_inches,
    ft_in,
    nm_to_ft_in,
    parse_feet_inches,
)


def test_constants_exact():
    assert NM_PER_INCH == 25_400_000
    assert NM_PER_FOOT == 304_800_000
    assert NM_PER_INCH % 64 == 0  # 1/64" must be an exact integer nm


@pytest.mark.parametrize(
    "text,expected_nm",
    [
        ("8'-7\"", 8 * NM_PER_FOOT + 7 * NM_PER_INCH),
        ("8' - 7\"", 8 * NM_PER_FOOT + 7 * NM_PER_INCH),
        ("8'7\"", 8 * NM_PER_FOOT + 7 * NM_PER_INCH),
        ("8'", 8 * NM_PER_FOOT),
        ('7"', 7 * NM_PER_INCH),
        ("0'-10\"", 10 * NM_PER_INCH),
        ("0' - 10\"", 10 * NM_PER_INCH),
        (" 6'-3\"", 6 * NM_PER_FOOT + 3 * NM_PER_INCH),
        ("6'-5\"", 6 * NM_PER_FOOT + 5 * NM_PER_INCH),
        ("7' - 0\"", 7 * NM_PER_FOOT),
        ("8' - 7 1/2\"", 8 * NM_PER_FOOT + 7 * NM_PER_INCH + NM_PER_INCH // 2),
        ('1/2"', NM_PER_INCH // 2),
        ("1/64\"", NM_PER_INCH // 64),
        ("-3'-6\"", -(3 * NM_PER_FOOT + 6 * NM_PER_INCH)),
    ],
)
def test_parse_known_values(text, expected_nm):
    assert parse_feet_inches(text) == expected_nm


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not a dimension",
        "CLG HT - 8' 5\"",  # known false-positive guard — Appendix A/D
        "CLG HT - 6'  3\"",
        "1/0\"",  # zero denominator
        "8''",
    ],
)
def test_rejects_non_dimensions(text):
    with pytest.raises(ParseError):
        parse_feet_inches(text)


def test_none_rejected():
    with pytest.raises(ParseError):
        parse_feet_inches(None)


@pytest.mark.parametrize(
    "nm,expected",
    [
        (8 * NM_PER_FOOT + 7 * NM_PER_INCH, "8'-7\""),
        (7 * NM_PER_INCH, '7"'),
        (8 * NM_PER_FOOT, "8'"),
        (10 * NM_PER_INCH, "10\""),
        (0, '0"'),
        (NM_PER_INCH // 2, '1/2"'),
        (8 * NM_PER_FOOT + 7 * NM_PER_INCH + NM_PER_INCH // 2, "8'-7 1/2\""),
        (-(3 * NM_PER_FOOT + 6 * NM_PER_INCH), "-3'-6\""),
    ],
)
def test_format_known_values(nm, expected):
    assert format_feet_inches(nm) == expected


# --- The Appendix A fixture measurements: these must parse exactly. ---

@pytest.mark.parametrize(
    "text,ft,inch",
    [
        ("8'-7\"", 8, 7),   # kitchen island length
        ("4'-3\"", 4, 3),   # kitchen island width
        ("60\" TV", None, None),  # NOT a dimension string — annotation text
    ],
)
def test_island_dimensions(text, ft, inch):
    if ft is None:
        with pytest.raises(ParseError):
            parse_feet_inches(text)
        return
    assert parse_feet_inches(text) == ft * NM_PER_FOOT + inch * NM_PER_INCH


def test_south_wall_chain_sums_to_overall():
    # 3'-1" + 5'-0" + 3'-1" chain on LIVING_ROOM.SOUTH (Appendix A)
    a = parse_feet_inches("3'-1\"")
    b = parse_feet_inches("5'-0\"")
    c = parse_feet_inches("3'-1\"")
    assert a + b + c == parse_feet_inches("11'-2\"")


def test_riser_math():
    # basement: 3 risers @ 7" each
    riser = parse_feet_inches('7"')
    assert riser * 3 == parse_feet_inches("1'-9\"")


# --- Round-trip properties ---

@given(st.integers(min_value=0, max_value=100 * NM_PER_FOOT).map(
    lambda n: (n // (NM_PER_INCH // 64)) * (NM_PER_INCH // 64)
))
def test_roundtrip_exact_64th_inch(nm):
    text = format_feet_inches(nm)
    assert parse_feet_inches(text) == nm


@pytest.mark.parametrize("denominator", [1, 2, 4, 8, 16, 32, 64])
@given(data=st.data())
def test_roundtrip_at_denominator(denominator, data):
    unit = NM_PER_INCH // denominator
    n_units = data.draw(st.integers(min_value=0, max_value=50 * 12 * denominator))
    nm = n_units * unit
    text = format_feet_inches(nm, denominator=denominator)
    assert parse_feet_inches(text) == nm


def test_negative_roundtrip():
    nm = -(5 * NM_PER_FOOT + 3 * NM_PER_INCH + NM_PER_INCH // 4)
    text = format_feet_inches(nm)
    assert parse_feet_inches(text) == nm


def test_bad_denominator_rejected():
    with pytest.raises(ValueError):
        format_feet_inches(NM_PER_INCH, denominator=3)


def test_aliases_match():
    assert ft_in("8'-7\"") == parse_feet_inches("8'-7\"")
    assert nm_to_ft_in(8 * NM_PER_FOOT) == format_feet_inches(8 * NM_PER_FOOT)
