__all__ = ["MAX_EAN13", "parse_ean13", "EAN13Mixin", "EAN13Code"]
from abc import ABC
from collections.abc import Sequence
from typing import (
    ClassVar,
    Final,
    Self,
)

from ..util.functions import immutable
from ..util.parse import (
    CheckDigitError,
    Mod10CheckDigits,
    WellFormednessError,
    mod10_check_digit,
    remove_ascii_spaces,
)
from ..util.standard import NumericStandardIdentifier

MAX_EAN13: Final[int] = 999_9_9999_9999


def parse_ean13(source: str, /) -> int:
    if len(source) != 13:
        raise WellFormednessError(f"EAN13 must contain 13 digits: {source!r}")
    number = int(source[:-1], base=10)
    cd = mod10_check_digit(number)
    if cd != source[-1]:
        raise CheckDigitError(
            f"Invalid EAN13 mod 10 check digit: expected {cd!r}, got {source[-1]!r}"
        )
    return number


class EAN13Mixin(ABC):
    __slots__ = ()

    # Just add a number to the implementing class,
    number: int

    @property
    def gs1(self) -> str:
        return f"{self.number:012d}"[0:3]

    @property
    def elements(self) -> str:
        return f"{self.number:012d}"[3:]

    @property
    def ean13_check_digit(self) -> Mod10CheckDigits:
        return mod10_check_digit(self.number)


@immutable
class EAN13Code(EAN13Mixin, NumericStandardIdentifier):
    EAN13_RANGES: ClassVar[Sequence[range]] = (range(0, MAX_EAN13 + 1),)

    def __new__(cls, number: int, /) -> Self:
        if not 0 <= number <= MAX_EAN13:
            raise WellFormednessError(f"EAN13 out of range: {number!r}")
        return NumericStandardIdentifier.__new__(cls, number)

    def collate(self) -> str:
        return f"{self.number:012d}{self.ean13_check_digit}"

    def __str__(self) -> str:
        return f"{self.gs1}-{self.elements}-{self.ean13_check_digit}"

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(f"EAN13 not in ASCII: {source!r}")
        s = remove_ascii_spaces(source.replace("-", ""))
        return NumericStandardIdentifier.__new__(cls, parse_ean13(s))

    presentation = __str__
