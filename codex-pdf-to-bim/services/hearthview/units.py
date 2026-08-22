import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction


TICKS_PER_INCH = 1024


class LengthParseError(ValueError):
    """Raised when a homeowner-entered length is ambiguous or inexact."""


_HELP = 'Use a length such as 5\' 0", 60 in, or 1524 mm.'


def _fail() -> LengthParseError:
    return LengthParseError(_HELP)


def _number(value: str) -> Fraction:
    value = " ".join(value.strip().split())
    mixed = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", value)
    fraction = re.fullmatch(r"(\d+)\s*/\s*(\d+)", value)
    try:
        if mixed:
            whole, numerator, denominator = map(int, mixed.groups())
            return Fraction(whole) + Fraction(numerator, denominator)
        if fraction:
            numerator, denominator = map(int, fraction.groups())
            return Fraction(numerator, denominator)
        return Fraction(Decimal(value))
    except (InvalidOperation, ValueError, ZeroDivisionError) as error:
        raise _fail() from error


def _to_ticks(inches: Fraction) -> int:
    ticks = inches * TICKS_PER_INCH
    if ticks < 0 or ticks.denominator != 1:
        raise _fail()
    return ticks.numerator


def parse_length(text: str) -> int:
    normalized = text.strip().lower().replace("′", "'").replace("″", '"')
    if not normalized or normalized.startswith("-"):
        raise _fail()

    metric = re.fullmatch(r"(.+?)\s*mm", normalized)
    if metric:
        millimeters = _number(metric.group(1))
        return _to_ticks(millimeters * Fraction(10, 254))

    feet_match = re.fullmatch(r"(\d+)\s*'\s*-?\s*(.*?)\s*\"?", normalized)
    if feet_match:
        feet = int(feet_match.group(1))
        inch_text = feet_match.group(2).strip()
        inches = Fraction(0) if not inch_text else _number(inch_text)
        if inches >= 12:
            raise _fail()
        return _to_ticks(Fraction(feet * 12) + inches)

    inches_match = re.fullmatch(r"(.+?)\s*(?:in|\")", normalized)
    if inches_match:
        return _to_ticks(_number(inches_match.group(1)))

    raise _fail()


def format_length(ticks: int) -> str:
    if ticks < 0:
        raise ValueError("Length ticks cannot be negative.")
    total_inches = Fraction(ticks, TICKS_PER_INCH)
    feet = total_inches.numerator // (12 * total_inches.denominator)
    inches = total_inches - feet * 12
    whole_inches = inches.numerator // inches.denominator
    remainder = inches - whole_inches
    if remainder:
        inch_display = f"{whole_inches} {remainder.numerator}/{remainder.denominator}"
    else:
        inch_display = str(whole_inches)
    return f"{feet}'-{inch_display}\""
