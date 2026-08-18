"""Exact integer-nanometre unit conversions and feet-inch parsing.

The storage unit for every length in the pipeline is int64 nanometres.
Feet-and-inches (and metric) are display/input formats only, never storage:
architectural fractions down to 1/64" are exactly representable in
nanometres, because 25_400_000 (one inch in nm) divides evenly by 64.
"""
from __future__ import annotations

import re
from fractions import Fraction

NM_PER_INCH: int = 25_400_000
NM_PER_FOOT: int = NM_PER_INCH * 12
NM_PER_MM: int = 1_000_000
NM_PER_M: int = 1_000 * NM_PER_MM

assert NM_PER_INCH % 64 == 0, "1 inch in nm must divide evenly by 64 for exact 1/64\" fractions"
NM_PER_64TH_INCH: int = NM_PER_INCH // 64


class ParseError(ValueError):
    """Raised when a string cannot be parsed as a feet-inches/fraction dimension."""


# Accepts the whitespace and punctuation variants actually found on
# architectural PDF sheets: "8'-7\"", "8' - 7\"", "8'7\"", "7\"",
# "7 1/2\"", "1/2\"", "11/64\"", "8'", "0'-10\"". Anchored so free text
# like "CLG HT - 8' 5\"" (a false-positive dimension look-alike) is
# rejected. The two-branch alternation for the inch component keeps a
# whole-inch number ("11") from being misread as a fraction numerator
# glued to the next digit run ("11/64" is one fraction, not "1" + "1/64"):
# branch A requires whitespace before a trailing fraction, branch B is a
# fraction with no whole part at all.
_TOKEN = re.compile(
    r"""
    ^\s*
    (?P<sign>-)?
    \s*
    (?:(?P<feet>\d+)\s*'\s*)?
    (?:-\s*)?
    (?:
        (?P<inch_whole>\d+)(?:\s+(?P<frac_num_a>\d+)\s*/\s*(?P<frac_den_a>\d+))?
        |
        (?P<frac_num_b>\d+)\s*/\s*(?P<frac_den_b>\d+)
    )?
    \s*"?
    \s*$
    """,
    re.VERBOSE,
)


def parse_feet_inches(text: str) -> int:
    """Parse a feet-inches / fraction dimension string to exact int nanometres.

    Raises ParseError on anything that isn't a clean dimension token
    (including empty/garbage input), so callers can distinguish "not a
    dimension" from "zero".
    """
    if text is None:
        raise ParseError("None is not a dimension string")
    raw = text.strip()
    if raw == "":
        raise ParseError("empty string is not a dimension")

    m = _TOKEN.match(raw)
    if not m or not any(
        m.group(name) for name in ("feet", "inch_whole", "frac_num_a", "frac_num_b")
    ):
        raise ParseError(f"could not parse {text!r} as a feet-inches dimension")

    feet = int(m.group("feet") or 0)
    inch_whole = int(m.group("inch_whole") or 0)
    total_nm = feet * NM_PER_FOOT + inch_whole * NM_PER_INCH

    frac_num = m.group("frac_num_a") or m.group("frac_num_b")
    if frac_num is not None:
        num = int(frac_num)
        den = int(m.group("frac_den_a") or m.group("frac_den_b"))
        if den == 0:
            raise ParseError(f"zero denominator in {text!r}")
        frac_nm = Fraction(num, den) * NM_PER_INCH
        if frac_nm.denominator != 1:
            raise ParseError(
                f"fraction {num}/{den}\" in {text!r} is not exactly "
                "representable in nanometres"
            )
        total_nm += int(frac_nm)

    if m.group("sign"):
        total_nm = -total_nm

    return total_nm


def format_feet_inches(nm: int, denominator: int = 64) -> str:
    """Format exact int nanometres as a feet-inches string, e.g. 8'-7 1/2".

    `denominator` controls fraction rounding granularity (default 1/64",
    the finest architectural fraction) and must evenly divide NM_PER_INCH.
    Rounding to the nearest 1/denominator inch uses round-half-to-even
    (Python's Fraction rounding) on a fixed computation order, so the same
    input always yields a byte-identical string.
    """
    if NM_PER_INCH % denominator != 0:
        raise ValueError(f"denominator {denominator} does not divide NM_PER_INCH exactly")

    sign = "-" if nm < 0 else ""
    n = abs(nm)

    unit_nm = NM_PER_INCH // denominator
    total_units = round(Fraction(n, unit_nm))

    feet, rem_units = divmod(total_units, denominator * 12)
    inch_whole, frac_units = divmod(rem_units, denominator)

    frac_str = ""
    if frac_units:
        f = Fraction(frac_units, denominator)
        frac_str = f" {f.numerator}/{f.denominator}"

    if feet and (inch_whole or frac_units):
        return f"{sign}{feet}'-{inch_whole}{frac_str}\""
    if feet:
        return f"{sign}{feet}'"
    if inch_whole or not frac_units:
        return f"{sign}{inch_whole}{frac_str}\""
    return f"{sign}{frac_str.strip()}\""


def ft_in(text: str) -> int:
    """Alias for parse_feet_inches, matching the plan's §5.1 naming."""
    return parse_feet_inches(text)


def nm_to_ft_in(nm: int) -> str:
    """Alias for format_feet_inches, matching the plan's §5.1 naming."""
    return format_feet_inches(nm)


def mm_to_nm(mm: float) -> int:
    """Exact for integer/half/quarter mm inputs; float mm is rounded to the nearest nm."""
    return round(mm * NM_PER_MM)


def nm_to_mm(nm: int) -> float:
    return nm / NM_PER_MM
