import pytest
from hypothesis import given, strategies as st

from hearthview.units import LengthParseError, TICKS_PER_INCH, format_length, parse_length


@pytest.mark.parametrize(
    ("text", "ticks"),
    [
        ("5' 0\"", 60 * TICKS_PER_INCH),
        ("5'-0\"", 60 * TICKS_PER_INCH),
        ("8'-7\"", 103 * TICKS_PER_INCH),
        ("60 in", 60 * TICKS_PER_INCH),
        ("3 1/2 in", 3 * TICKS_PER_INCH + TICKS_PER_INCH // 2),
        ("1524 mm", 60 * TICKS_PER_INCH),
    ],
)
def test_parse_length_accepts_homeowner_friendly_exact_values(text: str, ticks: int) -> None:
    assert parse_length(text) == ticks


@pytest.mark.parametrize("text", ["", "banana", "-1 in", "1/3 in", "5 feet maybe"])
def test_parse_length_rejects_ambiguous_or_unsupported_values(text: str) -> None:
    with pytest.raises(LengthParseError, match="Use a length such as"):
        parse_length(text)


@given(st.integers(min_value=0, max_value=1000 * 12))
def test_whole_inch_values_round_trip_without_drift(inches: int) -> None:
    ticks = inches * TICKS_PER_INCH
    assert parse_length(format_length(ticks)) == ticks


def test_format_length_preserves_exact_half_inches() -> None:
    assert format_length(61 * TICKS_PER_INCH + TICKS_PER_INCH // 2) == "5'-1 1/2\""
