# SPDX-License-Identifier: MIT
"""Implements a number of common string-related operations and constants, excluding those defined in URI-related RFCs such as RFC3986."""

__all__ = [
    "Collated",
    "CollatedName",
    "CodePoint",
    "NormalizationForm",
    "MAX_UNICODE",
    "MAX_ASCII",
    "CSS_ARGUMENT_CHARS",
    "ValidityError",
    "WellFormednessError",
    "CheckDigitError",
    "make_wellformed",
    "to_code_point",
    "from_code_point",
    "ascii_casefold",
    "remove_ascii_spaces",
    "pascal_case",
    "screaming_snake_case",
    "collate",
    "collate_uax44_lm2",
    "LooseMatchStrEnum",
    "loose_match_boolean",
    "Parseable",
    "Mod10CheckDigit",
    "Mod11CheckDigit",
    "mod11_check_digit",
    "mod10_check_digit",
]
import string
import sys
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Iterable
from enum import StrEnum
from string import ascii_letters, digits
from typing import ClassVar, Literal, NewType, Self, cast

Collated = NewType("Collated", str)
CollatedName = NewType("CollatedName", str)
CodePoint = NewType("CodePoint", int)
type NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]
type Mod10CheckDigit = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
type Mod11CheckDigit = Literal[Mod10CheckDigit, "X"]

MAX_UNICODE = CodePoint(0x10FFFF)
MAX_ASCII = CodePoint(0x007F)

ASCII_ALNUM = string.ascii_letters + string.digits
CSS_ARGUMENT_CHARS = ASCII_ALNUM + ".+-%"


class ValidityError(ValueError):
    """Subclass of :class:`ValueError` to indicate input with possibly recognizable syntax but invalid semantics.
    The distinction between :class:`ValidityError` and :class:`WellFormednessError` is often not clear-cut.

    The use of any of these specific subclasses over :class:`ValueError` shall be considered a courtesy feature.
    Callers should catch :class:`ValueError` instead of these specific subclasses.
    """

    pass


class WellFormednessError(ValueError):
    """Subclass of :class:`ValueError` to indicate that the input does not conform to standardized format.
    The distinction between :class:`ValidityError` and :class:`WellFormednessError` is often not clear-cut.

    The use of any of these specific subclasses over :class:`ValueError` shall be considered a courtesy feature.
    Callers should catch :class:`ValueError` instead of these specific subclasses.
    """

    pass


class CheckDigitError(ValidityError):
    """Subclass of :class:`ValidityError` to indicate input with invalid check digits.

    The use of any of these specific subclasses over :class:`ValueError` shall not form part of a public API specification.
    Callers should catch :class:`ValueError` instead of these specific subclasses.
    """

    pass

def make_wellformed(
    s: str,
    /,
    name: str = "Source",
    *,
    ascii_only: bool = False,
    strip: bool | str = False,
    lstrip: bool | str = False,
    rstrip: bool | str = False,
    casefold: bool = False,
    upper: bool = False,
    normalize: NormalizationForm | None = None,
    removeprefix: str | None = None,
    removesuffix: str | None = None,
    length: int | tuple[int, int] | None = None,
    no_whitespaces: bool = False,
    no_multilines: bool = False,
    is_alpha: bool = False,
    is_digit: bool = False,
    is_alnum: bool = False,
    startswith:  str | Collection[str] | None = None,
    endswith:  str | Collection[str] | None = None,
    first_chars: Collection[str] | Callable[[str], bool] | None = None,
    continue_chars: Collection[str] | Callable[[str], bool] | None = None,
    intern: bool = False,
) -> str:
    """Performs common string transformations and well-formedness checks.
    The order of operations is:
    1. `ascii_only` check
    2. case, normalization and prefix/suffix removal transformations
    3. length and allowed character checks
    4. string interning

    Operations are specified by keyword arguments. By default,
    no action is performed and the input string is returned as-is.
    `name` is the human-readable name in `WellFormednessError` message.
    `length` can be an integer or a tuple of (min, max) inclusive.
    """
    # Some of the operations are better represented in regular expressions.
    # Nonetheless, in many cases, using a function can be more maintainable.
    if ascii_only and not s.isascii():
        raise WellFormednessError(f"{name} not in ASCII: {s!r}")
    if strip:
        s = s.strip(strip if isinstance(strip, str) else None)
    if lstrip:
        s = s.lstrip(lstrip if isinstance(lstrip, str) else None)
    if rstrip:
        s = s.rstrip(rstrip if isinstance(rstrip, str) else None)
    if casefold:
        s = s.casefold()
    if upper:
        s = s.upper()
    if normalize:
        s = unicodedata.normalize(normalize, s)
    if removeprefix:
        s = s.removeprefix(removeprefix)
    if removesuffix:
        s = s.removesuffix(removesuffix)
    match length:
        case None:
            pass
        case int(i):
            if len(s) != i:
                raise WellFormednessError(
                    f"{name} must be of length {i}, got length {len(s)}: {s!r}"
                )
        case [int(minimum), 0]:
            if len(s) < minimum:
                raise WellFormednessError(
                    f"{name} must be at least length {minimum}"
                    f"got length {len(s)}: {s!r}"
                )
        case [0, int(maximum)]:
            if len(s) > maximum:
                raise WellFormednessError(
                    f"{name} must be at most length {maximum}"
                    f"got length {len(s)}: {s!r}"
                )
        case [int(minimum), int(maximum)]:
            if not minimum <= len(s) <= maximum:
                raise WellFormednessError(
                    f"{name} must be of length between {minimum} and {maximum}, "
                    f"got length {len(s)}: {s!r}"
                )
        case _:
            raise TypeError
    if no_whitespaces and len(s.split()) > 1:
        raise WellFormednessError(f"{name} contains whitespaces: {s!r}")
    if no_multilines and len(s.splitlines()) > 1:
        raise WellFormednessError(f"{name} contains multiple lines: {s!r}")
    if is_alnum and not s.isalnum():
        raise WellFormednessError(f"{name} is not alphanumeric: {s!r}")
    if is_alpha and not s.isalpha():
        raise WellFormednessError(f"{name} is not alphabetic: {s!r}")
    if is_digit and not s.isdigit():
        raise WellFormednessError(f"{name} is not digits: {s!r}")
    if startswith is None:
        pass
    elif isinstance(startswith, str):
        if not s.startswith(startswith):
            raise WellFormednessError(
                f"{name} does not start with {startswith!r}: {s!r}"
            )
    elif not any(s.startswith(x) for x in startswith):
        raise WellFormednessError(f"{name} does not start with prefix: {s!r}")
    if endswith is None:
        pass
    elif isinstance(endswith, str):
        if not s.endswith(endswith):
            raise WellFormednessError(f"{name} does not end with {endswith!r}: {s!r}")
    elif not any(s.endswith(x) for x in endswith):
        raise WellFormednessError(f"{name} does not end with suffix: {s!r}")
    if first_chars is not None:
        fn = first_chars if callable(first_chars) else lambda c: c in first_chars
        if not fn(s[:1]):
            raise WellFormednessError(
                f"{name} starts with disallowed character: {s[:1]!r}"
            )
    # Usually, continue_chars is a superset of first_chars, but we make no assumptions here
    if continue_chars is not None:
        fn = (
            continue_chars
            if callable(continue_chars)
            else lambda c: c in continue_chars
        )
        for c in s[1:]:
            if not fn(c):
                raise WellFormednessError(
                    f"{name} continues with disallowed character: {c!r}"
                )
    if intern:
        return sys.intern(s)
    return s




def to_code_point(cp: str | int, /) -> CodePoint:
    if isinstance(cp, str):
        return CodePoint(ord(cp))
    if not 0 <= cp <= MAX_UNICODE:
        raise UnicodeError(f"Code point ouside of 0..U+10FFFF: {cp}")
    return CodePoint(cp)


def from_code_point(cp: str | int, /) -> str:
    if isinstance(cp, int):
        return chr(cp)
    if len(cp) != 1:
        raise ValueError(f"String of length != 1")
    return cp


def ascii_casefold(s: str, /, upper: bool) -> str:
    # Used in DOI's and possibly other occasions
    op = str.upper if upper else str.casefold
    return "".join(op(c) if c.isascii() else c for c in s)


def remove_ascii_spaces(s: str, /) -> str:
    return "".join(s.split())


def pascal_case(s: str, *, check_identifier: bool = True) -> str:
    """PascalCase a string such that it is suitable for use as a class name.
    This is designed to process long property names (second column and beyond in PropertyAliases.txt).
    The result loose-matches the input.

    For example, "kRSUnicode" becomes "KRSUnicode".
    """
    if not s:
        return ""
    output = "".join(
        w[0].upper() + w[1:] for w in s.replace(" ", "").replace("-", "_").split("_")
    )

    if output.isidentifier() or not check_identifier:
        return output
    return output + "_"


def screaming_snake_case(s: str, check_identifier: bool = True) -> str:
    """SCREAMING_SNAKE_CASE a string such that it is suitable for use as a name for constants.
    This is designed to process long value aliases (third column and beyond in PropertyValueAliases.txt).

    The result loose-matches the input, despite how it looks!

    For example, "Arabic_Presentation_Forms-A" becomes "ARABIC_PRESENTATION_FORMS_A".
    """
    if not s:
        return ""
    output = s.strip().upper().replace(" ", "_").replace("-", "_")

    if output.isidentifier() or not check_identifier:
        return output
    return output + "_"


def collate(prop: str, /) -> Collated:
    return Collated(
        "".join(
            c.casefold()
            for c in prop
            if c != "_" and not c.isspace() and unicodedata.category(c) != "Pd"
        )
    )


def collate_uax44_lm2(name: str, /) -> CollatedName:
    output = []
    name = f" {name} "
    for i, c in enumerate(name):
        match c:
            case " " | "_":
                continue
            case alpha if alpha in ascii_letters:
                output.append(alpha.lower())
            case digit if digit in digits:
                output.append(digit)
            case "-":
                if name[i - 1] in "_ " or name[i + 1] in "_ ":
                    # Non-medial hyphen
                    output.append("-")
            case _:
                raise UnicodeError(f"Invalid name: {name.strip()!r}")
    n = "".join(output)
    # Special case U+1180 HANGUL JUNGSEONG O-E
    if n == "hanguljungseongoe" and "o-e" in name.lower():
        return CollatedName("hanguljungseongo-e")
    return CollatedName(n)


def _remove_is_prefix(collated: Collated) -> Collated:
    # UAX44-LM3: remove the "is" prefix
    if collated.startswith("is") and len(collated) > 2:
        return Collated(collated[2:])
    return collated


class LooseMatchStrEnum(StrEnum):
    __collated__: ClassVar[bool] = False

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._precollate()

    @classmethod
    def _precollate(cls):
        if cls.__collated__:
            return
        existing = dict(cls.__members__)
        for k, v in existing.items():
            kc = collate(k)
            if kc not in existing:
                try:
                    v._add_alias_(kc)  # type: ignore
                except NameError:
                    pass  # Already assigned
            no_prefix = _remove_is_prefix(kc)
            if no_prefix != kc and no_prefix not in existing:
                try:
                    v._add_alias_(no_prefix)  # type: ignore
                except NameError:
                    pass  # No-prefix form has already been assigned
            vv = v.value
            vc = collate(vv)
            if vc != vv:
                try:
                    v._add_value_alias_(vc)  # type: ignore
                except ValueError:
                    pass
            vnp = _remove_is_prefix(vc)
            if vnp != vc:
                try:
                    v._add_value_alias_(vnp)  # type: ignore
                except ValueError:
                    pass
        cls.__collated__ = True

    @classmethod
    def _missing_(cls, value: str, /) -> Self:
        try:
            return cls.__members__[value]
        except KeyError:
            pass

        collated = _remove_is_prefix(collate(value))
        if collated != value:
            try:
                return cls.__members__[collated]
            except KeyError:
                try:
                    return cls(collated)
                except ValueError as ve:
                    raise ve
        raise ValueError(value)


def loose_match_boolean(v: str) -> bool:
    if v in {"", "Y", "Yes", "True", "T"}:
        return True
    return collate(v) in {"y", "yes", "true", "t"}


class Parseable(ABC):
    """This class is intended for subclasses whose instances have states that can be entirely
    represented as a standardized string.
    The basic contract of the class is the round-trip convertibility via the `parse` and `__str__` methods.
    Namely, `parse(str(obj)) == obj`.

    This class also adds automatic pickle and database support based on this contract.
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def parse(cls, source: str, /) -> Self:
        """Parses the given `source` string and returns an instance.
        Raises :class:`ValueError` or its subclass on malformed or invalid input.

        It must accept all valid forms according to the published standard.
        Implementations may accept other forms of input or even salvage bad input, but this must be done in a safe manner.
        """
        ...

    @abstractmethod
    def __str__(self):
        """Returns the string form according to a published standard.
        (This is not the same thing as the ``__repr__`` form as used in Python.)
        This string must be accepted by the `parse` class method: `parse(str(self)) == self`.
        The string may be collated, though it is better for the class itself to implement rich comparison for sorting.

        Good examples of such strings include `http://example.com/` for a URI,
        `1970-01-01` for a date and `#336699aa` for a color.
        """
        ...

    def __reduce__(self):
        """Returns a **reduce object** for use in `pickle` and `copy` protocols.
        The default implementation consists of the `parse` class method, and the `__str__` output.

        Implementing classes are free to use any data types as they see fit.
        There is no requirement for implementing classes to use strings as their pickled representation.
        Nonetheless, using strings is more secure against malformed input and is forward-compatible should the
        structured representation change.
        """
        # Callable, args, state for __setstate__, iter, iter(k, v), callable(obj, state)
        return self.parse, (str(self),)

    def __conform__(self, protocol) -> None | int | float | str | bytes:
        """An adapter method for storing values into databases.
        The default implementation returns the `str()` output regardless of protocol.

        Implementing classes are free to use any data types as they see fit.
        There is no requirement for implementing classes to use strings as their database representation.
        Nonetheless, using strings avoids the database pitfalls with data types.
        """
        return str(self)

    @classmethod
    def converter(cls, db_value: bytes) -> Self:
        """A converter method for registration of sqlite3 converters.
        The default implementation decodes the incoming sqlite3 blob as UTF-8 string
        and then `parse()` it into an instance.

        An example is to call `sqlite3.register_converter("point", Point.converter)`

        Implementing classes are free to use any data types as they see fit.
        There is no requirement for implementing classes to use strings as their database representation.
        Nonetheless, using strings avoids the database pitfalls with data types.
        """
        return cls.parse(db_value.decode())


def mod11_check_digit(i_no_check_digit: int) -> Mod11CheckDigit:
    div = i_no_check_digit
    s = 0
    weight = 2
    while div > 0:
        div, mod = divmod(div, 10)
        s += mod * weight
        weight += 1
    m = 11 - s % 11
    if m == 11:
        return "0"
    elif m == 10:
        return "X"
    else:
        return cast(Mod10CheckDigit, string.digits[m])


def mod10_check_digit(i_no_check_digit: int) -> Mod10CheckDigit:
    div = i_no_check_digit
    s = 0
    weight = 3
    while div > 0:
        div, mod = divmod(div, 10)
        s += mod * weight
        weight = 1 if weight == 3 else 3
    return cast(Mod10CheckDigit, string.digits[(10 - s % 10) % 10])


def split_escape[P](
    s: str,
    /,
    separator: str = ",",
    escape: str | None = "\\",
    lstrip: bool = True,
    rstrip: bool = True,
    keep_empty: bool = True,
    output_fn: Callable[[str], P] = str,
) -> Iterable[P]:
    buf = []
    in_escape = False
    for c in s:
        if in_escape:
            if c != escape and c != separator:
                # We don't hold onto escape sequences we don't recognize
                buf.append(escape)
            buf.append(c)
            in_escape = False
        elif c == escape:
            in_escape = True
        elif c == separator:
            s = "".join(buf)
            if lstrip:
                s = s.lstrip()
            if rstrip:
                s = s.rstrip()
            if s or keep_empty:
                yield output_fn(s)
            buf.clear()
        else:
            buf.append(c)
    if buf:
        s = "".join(buf)
        if lstrip:
            s = s.lstrip()
        if rstrip:
            s = s.rstrip()
        if s or keep_empty:
            yield output_fn(s)
