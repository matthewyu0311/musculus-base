# SPDX-License-Identifier: MIT
"""Implements a number of common string-related operations and constants, excluding those defined in URI-related RFCs such as RFC3986."""

__all__ = [
    "CSS_ARGUMENT_CHARS",
    "CheckDigitError",
    "Parseable",
    "ValidityError",
    "WellFormednessError",
    "ascii_casefold",
]
import string
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar, Literal, Self, cast

CSS_ARGUMENT_CHARS = frozenset(string.ascii_letters + string.digits + ".+-%")


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


def ascii_casefold(s: str, /, upper: bool) -> str:
    # Used in DOI's and possibly other occasions
    op = str.upper if upper else str.casefold
    return "".join(op(c) if c.isascii() else c for c in s)


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


type Mod10CheckDigits = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
type Mod11CheckDigits = Literal[Mod10CheckDigits, "X"]


def mod11_check_digit(i_no_check_digit: int) -> Mod11CheckDigits:
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
        return cast(Mod10CheckDigits, string.digits[m])


def mod10_check_digit(i_no_check_digit: int) -> Mod10CheckDigits:
    div = i_no_check_digit
    s = 0
    weight = 3
    while div > 0:
        div, mod = divmod(div, 10)
        s += mod * weight
        weight = 1 if weight == 3 else 3
    return cast(Mod10CheckDigits, string.digits[(10 - s % 10) % 10])


def remove_ascii_spaces(s: str, /) -> str:
    return "".join(s.split())

