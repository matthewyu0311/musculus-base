__all__ = ["MIN_ISMN", "MAX_ISMN", "ISMN"]

from collections.abc import Sequence
from typing import Final, Self

from ..util.functions import immutable
from ..util.parse import WellFormednessError, remove_ascii_spaces
from ..util.standard import NumericStandardIdentifier
from .ean13 import EAN13Mixin, parse_ean13
from .urn import URN_SCHEME, URNMixin

MIN_ISMN: Final[int] = 979_0_0000_0000
MAX_ISMN: Final[int] = 979_0_9999_9999
_ISMN_REGISTRANT_LENGTH = (3, 4, 4, 4, 5, 5, 5, 6, 6, 7)


@immutable
class ISMN(EAN13Mixin, URNMixin, NumericStandardIdentifier):
    """
    This class implements International Standard Music Number.
    The number format is EAN13.
    ISMN is compatible with URN with Namespace ID "ismn".
    ISMN does not provide a resolution service.
    """

    __slots__ = ()

    nid: Final[str] = "ismn"
    EAN13_RANGES: Final[Sequence[range]] = (range(MIN_ISMN, MAX_ISMN + 1),)

    check_digit = EAN13Mixin.ean13_check_digit

    @property
    def elements(self) -> str:
        return f"0-{self.registrant}-{self.item}"

    @property
    def registrant(self) -> str:
        # Skip the "0" in "9790"
        length = _ISMN_REGISTRANT_LENGTH[(self.number // 10000000) % 10]
        return self.collate()[4 : length + 4]

    @property
    def item(self) -> str:
        length = _ISMN_REGISTRANT_LENGTH[(self.number // 10000000) % 10]
        return self.collate()[length + 4 : -1]

    def __new__(cls, number: int, /):
        if 0 <= number <= MIN_ISMN:
            n = number + MIN_ISMN
        else:
            n = number
        if not any(n in r for r in cls.EAN13_RANGES):
            raise WellFormednessError(f"ISMN out of range: {number!r}")
        return NumericStandardIdentifier.__new__(cls, n)

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(f"ISMN not in ASCII: {source!r}")
        s = remove_ascii_spaces(
            source.casefold()
            .removeprefix(f"{URN_SCHEME}:")
            .removeprefix(cls.nid)
            .removeprefix(":")
            .replace("-", "")
        )
        if s.startswith("m"):
            s = "9790" + s[1:]
        if len(s) != 13:
            raise WellFormednessError(f"ISMN must be 13 or 10 digits, got {source!r}")
        number = parse_ean13(s)
        return cls(number)

    def __str__(self) -> str:
        return f"{self.gs1}-{self.elements}-{self.ean13_check_digit}"

    def collate(self) -> str:
        return f"{self.number:012d}{self.ean13_check_digit}"

    def presentation(self) -> str:
        # ISMN Users' Manual Section 2:
        # An International Standard Music Number (ISMN) consists of the prefix «979-0» followed by nine digits.
        # Whenever it is printed or written, the number is preceded by the letters «ISMN».
        # For ease of reading in print, the four elements of the ISMN are divided by spaces or hyphens. These
        # separators, however, are not retained in the computer which recognizes the elements on the basis of
        # the fixed ranges of numbers.

        return f"ISMN {self}"
