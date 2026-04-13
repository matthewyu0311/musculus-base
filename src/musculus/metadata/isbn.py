__all__ = ["MIN_ISBN", "MAX_ISBN", "ISBN"]

from collections.abc import Sequence
from typing import Final, Self

from ..util.functions import immutable
from ..util.parse import (
    CheckDigitError,
    WellFormednessError,
    mod11_check_digit,
    remove_ascii_spaces,
)
from ..util.standard import NumericStandardIdentifier
from .ean13 import EAN13Mixin, parse_ean13
from .ismn import MAX_ISMN, MIN_ISMN
from .urn import URN_SCHEME, URNMixin

MIN_ISBN: Final[int] = 978_000000000
MAX_ISBN: Final[int] = 979_999999999


@immutable
class ISBN(EAN13Mixin, URNMixin, NumericStandardIdentifier):
    """
    This class implements ISBN.
    The number format is EAN13.
    ISBN is compatible with URN with Namespace ID "isbn".
    ISBN does not provide a resolution service.
    """

    __slots__ = ()

    nid: Final[str] = "isbn"

    EAN13_RANGES: Final[Sequence[range]] = (
        range(MIN_ISBN, MIN_ISMN),
        range(MAX_ISMN + 1, MAX_ISBN + 1),
    )

    check_digit = EAN13Mixin.ean13_check_digit

    def __new__(cls, number: int) -> Self:
        if 0 <= number <= MIN_ISBN:
            n = number + MIN_ISBN
        else:
            n = number
        if not any(n in r for r in cls.EAN13_RANGES):
            raise WellFormednessError(f"ISBN out of range: {number!r}")
        return NumericStandardIdentifier.__new__(cls, n)

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(f"ISBN not in ASCII: {source!r}")
        s = remove_ascii_spaces(
            source.casefold()
            .removeprefix(f"{URN_SCHEME}:")
            .removeprefix(cls.nid)
            .removeprefix(":")
            .replace("-", "")
        )
        match len(s):
            case 13:
                number = parse_ean13(s)
            case 10:
                number = int(s) // 10
                cd = mod11_check_digit(number)
                if cd != s[-1]:
                    raise CheckDigitError(
                        f"Invalid ISBN check digit: expected {cd!r}, got {s[-1]!r}"
                    )
                number += MIN_ISBN
            case n:
                raise WellFormednessError(f"Malformed ISBN length of {n}: {source!r}")
        return cls(number)

    def __str__(self) -> str:
        s = f"{self.number:012d}"
        return f"{s[0:3]}-{s[3:]}-{self.ean13_check_digit}"

    def presentation(self) -> str:
        # ISBN Handbook Section 5:
        # When printed, the ISBN is always preceded by the letters "ISBN".
        return f"ISBN {self}"

    def collate(self) -> str:
        return f"{self.number:012d}{self.ean13_check_digit}"
