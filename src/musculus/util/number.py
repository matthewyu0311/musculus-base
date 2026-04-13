__all__ = [
    "HALF_PI",
    "FracOrFloat",
    "FracOrInt",
    "frac",
    "sign",
    "all_sign",
    "clamp",
    "UnsignedRoundingMode",
    "RoundingMode",
    "css_round_towards_nearest_integer",
    "round_up",
    "frac_float",
    "frac_int",
    "int10",
    "roman",
    "parse_roman",
    "to_decimal_places",
    "adjust_decimal_places",
    "DEGREE_SIGN",
    "PRIME",
    "DOUBLE_PRIME",
    "SI_PREFIXES",
    "make_quantity",
    "scale_quantity",
    "split_quantity",
    "parse_quantity",
    "angle_difference",
    "parse_css_angle",
    "parse_percent",
]
# SPDX-License-Identifier: MIT

from enum import Enum
from fractions import Fraction
from functools import lru_cache, partial
from math import ceil, degrees, floor, isnan, pi
from numbers import Rational, Real
from typing import Literal, Self, TypeAlias, cast
from unicodedata import normalize

# We don't have this in standard library math
HALF_PI = pi / 2

# These one have to be an explicit TypeAlias since it gets isinstance'd
FracOrFloat: TypeAlias = int | float | Fraction
FracOrInt: TypeAlias = Fraction | int

_FRACTION_LRU_SIZE = 1024
_FRACTIONS = {}


@lru_cache(maxsize=_FRACTION_LRU_SIZE)
def _get_fraction(k):
    return Fraction(*k)


def frac(
    numerator: FracOrFloat | str, denominator: FracOrFloat | str | None = None
) -> Fraction:
    """Fraction factory for LRU-cached fractions."""
    if denominator is None or denominator == 1:
        if isinstance(numerator, Fraction):
            return numerator
        denominator = None
    elif denominator == 0:
        raise ZeroDivisionError("Denominator cannot be 0")
    k = (numerator, denominator)
    try:
        return _FRACTIONS[k]
    except KeyError:
        if denominator is None:
            return _get_fraction(k)
        return _get_fraction((numerator,)) / _get_fraction((denominator,))


def sign(x: FracOrFloat) -> Literal[-1, 0, 1]:
    if x > 0:
        return 1
    elif x < 0:
        return -1
    elif isnan(x):
        raise ArithmeticError("Cannot sign nan")
    else:
        return 0


def all_sign(*x: FracOrFloat) -> Literal[-1, 0, 1, None]:
    if not x:
        return None
    s = sign(x[0])
    for element in x[1:]:
        s2 = sign(element)
        if s2 == 0:
            # Zero does not affect the sign
            continue
        elif s == 0:
            # Existing sign is 0
            s = s2
        elif s2 != s:
            return None
    return s


def clamp[A: FracOrFloat, B: FracOrFloat, C: FracOrFloat](
    x: A, minimum: B = 0, maximum: C = 1
) -> A | B | C:
    if x < minimum:
        return minimum
    if x > maximum:
        return maximum
    return x


class UnsignedRoundingMode(Enum):
    ZERO = "ZERO"
    INFINITY = "INFINITY"
    HALF_INFINITY = "HALF_INFINITY"
    HALF_ZERO = "HALF_ZERO"
    HALF_EVEN = "HALF_EVEN"

    def round(self, x: FracOrFloat, r1: int, r2: int) -> int:
        if x == r1:
            return r1
        if not r1 < x < r2:
            raise ValueError(f"Number out of range: {x!r}")
        match self.value:
            case "ZERO":
                return r1
            case "INFINITY":
                return r2
            case "HALF_ZERO" | "HALF_INFINITY":
                d1 = x - r1
                d2 = r2 - x
                if d1 < d2:
                    return r1
                if d2 < d1:
                    return r2
                return r1 if self.value == "HALF_ZERO" else r2
            case "HALF_EVEN":
                cardinality = (r1 / (r2 - r1)) % 2
                return r2 if cardinality else r1


class RoundingMode(Enum):
    CEIL = UnsignedRoundingMode.INFINITY, UnsignedRoundingMode.ZERO
    FLOOR = UnsignedRoundingMode.ZERO, UnsignedRoundingMode.INFINITY
    EXPAND = UnsignedRoundingMode.INFINITY, UnsignedRoundingMode.INFINITY
    TRUNC = UnsignedRoundingMode.ZERO, UnsignedRoundingMode.ZERO
    HALF_CEIL = UnsignedRoundingMode.HALF_INFINITY, UnsignedRoundingMode.HALF_ZERO
    HALF_FLOOR = UnsignedRoundingMode.HALF_ZERO, UnsignedRoundingMode.HALF_INFINITY
    HALF_EXPAND = UnsignedRoundingMode.HALF_INFINITY, UnsignedRoundingMode.HALF_INFINITY
    HALF_TRUNC = UnsignedRoundingMode.HALF_ZERO, UnsignedRoundingMode.HALF_ZERO
    HALF_EVEN = UnsignedRoundingMode.HALF_EVEN, UnsignedRoundingMode.HALF_EVEN

    @property
    def positive_unsigned(self) -> UnsignedRoundingMode:
        return self.value[0]

    @property
    def negative_unsigned(self) -> UnsignedRoundingMode:
        return self.value[1]

    def round(
        self, x: FracOrFloat, increment: int = 1, *, as_if_positive: bool = False
    ) -> int:
        quotient = x / increment
        if not as_if_positive and quotient < 0:
            quotient = -quotient
            sign = -1
            urm = self.negative_unsigned
        else:
            sign = 1
            urm = self.positive_unsigned
        r1 = floor(quotient)
        r2 = r1 + 1
        return sign * increment * urm.round(quotient, r1, r2)

    def __pos__(self) -> Self:
        return self

    def __neg__(self) -> RoundingMode:
        match self:
            case RoundingMode.CEIL:
                return RoundingMode.FLOOR
            case RoundingMode.FLOOR:
                return RoundingMode.CEIL
            case RoundingMode.HALF_CEIL:
                return RoundingMode.HALF_FLOOR
            case RoundingMode.HALF_FLOOR:
                return RoundingMode.HALF_CEIL
            case _:
                return self


def css_round_towards_nearest_integer(x: FracOrFloat) -> int:
    # CSS "rounding to the nearest integer" is to round ties towards +inf, which is HALF_CEIL
    return RoundingMode.HALF_CEIL.round(x)


def round_up(x: FracOrFloat, /) -> int:
    """Round 0.5 and -0.5 towards +inf"""
    if isinstance(x, int):
        return x
    f = floor(x)
    if x - f >= 0.5:
        return f + 1
    return f


def frac_float(x: FracOrFloat | Real | str, /) -> FracOrFloat:
    match x:
        case int():
            return x
        case Fraction():
            if x.is_integer():
                return x.numerator
            return x
        case str(s):
            try:
                return int(s)
            except ValueError:
                try:
                    return frac(s)
                except ValueError:
                    return float(s)
        case f:
            f = cast(float, f)  # Actually, can also be some other number types
            try:
                fint = int(f)
                if fint == f:
                    return fint
            except ValueError:
                pass
            if isinstance(f, float):
                return float(f)
            try:
                # Don't bother parsing this thing ourselves
                return Fraction(f)
            except ValueError, ArithmeticError:
                return float(f)


def frac_int(x: FracOrFloat | Rational | str, /) -> FracOrInt:
    match x:
        case int():
            return int(x)
        case Fraction():
            return x.numerator if x.is_integer() else x
        case str(s):
            try:
                return int(s)
            except ValueError:
                return frac(s)
        case _:
            x = Fraction(x)
            return x.numerator if x.is_integer() else x


int10 = partial(int, base=10)


################################################
# Roman numerals
################################################

_ROMAN_PLACE_VALUES = {
    1000: "M",
    900: "CM",
    500: "D",
    400: "CD",
    100: "C",
    90: "XC",
    50: "L",
    40: "XL",
    10: "X",
    9: "IX",
    5: "V",
    4: "IV",
    1: "I",
}

_INVERSE_ROMAN = {v.casefold(): k for k, v in reversed(_ROMAN_PLACE_VALUES.items())}


def _to_roman(n: int, buf: list[str]) -> list[str]:
    if n < 0:
        raise OverflowError(
            f"Negative number cannot be represented in Roman numeral: {n}"
        )
    # To constrain the level of recursion we can either forbid numbers >= 4000
    # or precalculate the "M"s like here
    m, n = divmod(n, 1000)
    buf.append("M" * m)
    for k, v in _ROMAN_PLACE_VALUES.items():
        if n >= k:
            n -= k
            buf.append(v)
            return _to_roman(n, buf)
    return buf


def roman(n: int, /) -> str:
    return "".join(_to_roman(n, []))


def parse_roman(s: str, /) -> int:
    if not s.isascii():
        s = normalize("NFKD", s)
    s = s.casefold()
    rest = s.lstrip("m")
    n = 1000 * (len(s) - len(rest))
    last_value = 1000
    for value in (_INVERSE_ROMAN.get(c, 0) for c in rest):
        n += value
        if value > last_value:
            n = n - last_value - last_value
        last_value = value
    return n


################################################
# Decimal places
################################################


def _count_decimal_places(s: str):
    try:
        dot_index = s.index(".")
        return len(s) - dot_index - 1
    except ValueError:
        return 0


def to_decimal_places(f: float, /, n: int = 8, *, strip: bool = True) -> str:
    s = f"%.{n}f" % f
    if strip:
        left, dot, right = s.partition(".")
        r = right.rstrip("0")
        if r:
            return left + dot + r
        return left
    return s


def adjust_decimal_places(*f: float) -> list[str]:
    strs = [to_decimal_places(d) for d in f]
    max_decimal_places = max(map(_count_decimal_places, strs))
    return [to_decimal_places(d, max_decimal_places) for d in f]


################################################
# Number parsing, units and CSS
################################################

# U+00B0 DEGREE SIGN
# U+2032 PRIME
# U+2033 DOUBLE PRIME
DEGREE_SIGN = "\u00b0"
PRIME = "\u2032"
DOUBLE_PRIME = "\u2033"


SI_PREFIXES: dict[int, tuple[str, ...]] = {
    30: ("quetta", "Q"),
    27: ("ronna", "R"),
    24: ("yotta", "Y"),
    21: ("zetta", "Z"),
    18: ("exa", "E"),
    15: ("peta", "P"),
    12: ("tera", "T"),
    9: ("giga", "G"),
    6: ("mega", "M"),
    3: ("kilo", "k"),
    2: ("hecto", "h"),
    1: ("deca", "da"),
    # 0: ("", ""),
    -1: ("deci", "d"),
    -2: ("centi", "c"),
    -3: ("milli", "m"),
    -6: ("micro", "μ", "u"),
    -9: ("nano", "n"),
    -12: ("pico", "p"),
    -15: ("femto", "f"),
    -18: ("atto", "a"),
    -21: ("zepto", "z"),
    -24: ("yocto", "y"),
    -27: ("ronto", "r"),
    -30: ("quecto", "q"),
}


def make_quantity(n: FracOrFloat, unit: str) -> str:
    return f"{to_decimal_places(float(n))}{unit}"


def scale_quantity(source: str, factor: FracOrFloat, /) -> str:
    n, unit = parse_quantity(source)
    return f"{to_decimal_places(float(factor * n))}{unit}"


def split_quantity(source: str, /) -> tuple[str, str]:
    # Assume source is in ASCII
    if not source.isascii():
        raise ValueError(f"Non-ASCII quantity: {source!r}")
    source = source.strip()
    ls = len(source)
    split_pos = ls
    for i in range(ls):
        c = source[i]
        try:
            d = source[i + 1]
        except IndexError:
            d = "foo"
        if c.isspace():
            split_pos = i
            break
        if c not in "+-0123456789.,_" and (c not in "eE" or d not in "+-0123456789"):
            split_pos = i
            break
    x = source[:split_pos].strip()
    unit = source[split_pos:].strip()
    return x, unit


def parse_quantity(source: str, /) -> tuple[FracOrInt, str]:
    x, unit = split_quantity(source)
    if "/" in x:
        raise ValueError(f"Illegal character: {x!r}")
    return frac_int(x), unit


def angle_difference(degree1: FracOrFloat, degree2: FracOrFloat) -> FracOrFloat:
    """Returns the difference in a circle between two compass bearings in degrees."""
    d = (degree1 - degree2) % 360
    if d > 180:
        # wrap around to negative
        return d - 360
    return d


def parse_css_angle(source: str, /) -> FracOrInt:
    """Parses a CSS angle quantity into degrees (360 degrees per full turn)."""
    num, unit = parse_quantity(source)
    match unit.casefold():
        case "deg" | "":
            return num
        case "rad":
            return frac(degrees(num))
        case "grad":
            return frac(num * 9, 10)
        case "turn":
            return num * 360
        case _:
            raise ValueError(f"Not a CSS angle unit: {unit!r}")


def parse_percent(source: str, /, full_scale_100_percent: FracOrInt = 1) -> Fraction:
    """Parses a dimesionless quantity into percentage."""
    x, unit = split_quantity(source)
    if "/" in x:
        raise ValueError(f"Illegal character: {x!r}")
    num = frac(x)
    if not unit:
        return num
    if unit == "%":
        return num * full_scale_100_percent / 100
    raise ValueError(f"Unexpected unit: {source!r}")
