# SPDX-License-Identifier: MIT
__all__ = [
    "MAX_ISAN",
    "MAX_ISAN_ROOT",
    "MAX_ISAN_EPISODE_OR_PART",
    "MAX_ISAN_VERSION",
    "ISAN",
    "isan_check_digits",
]
from collections.abc import Sequence
from string import ascii_uppercase, digits
from typing import Final, Self
from urllib.parse import SplitResult

from ..util.functions import immutable
from ..util.parse import CheckDigitError, WellFormednessError, remove_ascii_spaces
from ..util.standard import (
    NumericStandardIdentifier,
    PathResolver,
    PathResolverURIMixin,
)
from .urn import URN_SCHEME, URNMixin

MAX_ISAN: Final[int] = 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF
MAX_ISAN_ROOT: Final[int] = 0xFFFF_FFFF_FFFF
MAX_ISAN_EPISODE_OR_PART: Final[int] = 0xFFFF
MAX_ISAN_VERSION: Final[int] = 0xFFFF_FFFF


@immutable
class ISAN(PathResolverURIMixin, URNMixin, NumericStandardIdentifier):
    """This class implements ISAN.
    The number format is special, and cannot be converted to EAN13.
    ISAN provides a resolution service.
    ISAN is compatible with URN with Namespace ID "isan".
    """

    # From ISAN User Guide Section 2:
    # ISAN has been designed to be read by humans and processed in information systems, as a
    # 24-length hexadecimal number (characters 0 to 9 and A to F) or as a 96-bit binary number.

    # An ISAN is divided in three segments:
    # - the first 12 digits represent the root segment,
    # - the following 4 digits represent the episode/part of a serial work,
    # - the last 8 digits represent the version segment.

    # 2 check characters are included in presentation form.

    RESOLVER_BASES: Sequence[PathResolver] = (
        PathResolver.of_prefix("https://www.isan.org/lookup/"),
        PathResolver.of_prefix("http://www.isan.org/lookup/"),
    )
    nid: Final[str] = "isan"

    def __new__(cls, number: int, /):
        if not 0 <= number <= MAX_ISAN:
            raise WellFormednessError(
                f"ISAN binary value must be between 0000-0000-0000 to FFFF-FFFF-FFFF: {number:024X}"
            )
        return NumericStandardIdentifier.__new__(cls, number)

    @property
    def root(self) -> int:
        return self.number >> 48

    @property
    def episode_or_part(self) -> int:
        return (self.number & 0xFFFF_0000_0000) >> 32

    @property
    def version(self):
        return self.number & MAX_ISAN_VERSION

    @property
    def check1(self) -> str:
        return isan_check_digits(self.number)[0]

    @property
    def check2(self) -> str:
        return isan_check_digits(self.number)[1]

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(f"ISAN not in ASCII: {source!r}")
        s = source.casefold()
        if "isan.org" in s:
            return cls.from_resolver_uri(source)
        s = remove_ascii_spaces(
            s.removeprefix(f"{URN_SCHEME}:")
            .removeprefix(cls.nid)
            .removeprefix(":")
            .replace("-", "")
        )
        check1 = check2 = ""
        match len(s):
            case 24:
                # No check digits
                number = int(s, base=16)
            case 26:
                # 2 check digits
                check1 = s[16]
                check2 = s[25]
                number = int(s[0:16] + s[17:25], base=16)
            case 17:
                # 1 check digit, no version
                check1 = s[16]
                number = int(s[0:16], base=16) << 32
            case 16:
                # No check digit, no version
                number = int(s, base=16) << 32
            case 12:
                # No check digit, no episode, no version
                number = int(s, base=16) << 48
            case _:
                raise WellFormednessError(
                    f"ISAN must be 12, 16, 17, 24 or 26 hexadecimal digits: {source!r}"
                )
        if check1 or check2:
            calculated1, calculated2 = isan_check_digits(number)
            if check1 and check1.upper() != calculated1:
                raise CheckDigitError(
                    f"Provided first check character {check1!r} does not match calculated {calculated1!r}"
                )
            if check2 and check2.upper() != calculated2:
                raise CheckDigitError(
                    f"Provided second check character {check2!r} does not match calculated {calculated2!r}"
                )
        return cls(number)

    @classmethod
    def of(cls, root: int, episode_or_part: int = 0, version: int = 0) -> Self:
        """Constructs an ISAN from integer parts."""
        if not 0 <= root <= MAX_ISAN_ROOT:
            raise WellFormednessError(
                f"Root segment must be a 48-bit unsigned integeer: {root:012X}"
            )
        if not 0 <= episode_or_part <= MAX_ISAN_EPISODE_OR_PART:
            raise WellFormednessError(
                f"Episode-or-part segment must be 16-bit unsigned integeer: {episode_or_part:04X}"
            )
        if not 0 <= version <= MAX_ISAN_VERSION:
            raise WellFormednessError(
                f"Version segment must be 32-bit unsigned integeer: {version:08X}"
            )

        return cls(root << 48 | episode_or_part << 16 | version)

    def __str__(self) -> str:
        """Returns the 24-digits separated by hyphens and with two check characters."""
        check1, check2 = isan_check_digits(self.number)
        c = self.collate()
        return f"{c[0:4]}-{c[4:8]}-{c[8:12]}-{c[12:16]}-{check1}-{c[16:20]}-{c[20:24]}-{check2}"

    def collate(self) -> str:
        """Returns a collated representation with no hyphens or check characters.
        This is not considered a valid ISAN form by the specification."""
        return f"{self.number:024X}"

    def presentation(self) -> str:
        """Returns the printed form.

        ISAN User Guide Section 2.2 states that:
        When the ISAN is printed or otherwise displayed for the human-eye, it always includes the "ISAN"
        prefix and the two check characters."""
        return f"ISAN {self}"

    def to_resolver_uri(self) -> SplitResult:
        return self.RESOLVER_BASES[0].to_resolver_uri(self.presentation())

    @property
    def nss(self) -> str:
        """ISAN URN NSS, unlike other identifiers, retains the separators."""
        return str(self)


def isan_check_digits(number: int, /) -> tuple[str, str]:
    adjusted_product = 0
    check1 = "0"
    for i in range(24):
        digit_value = (number >> (92 - i * 4)) & 0xF
        adjusted_product = ((((adjusted_product + digit_value) % 36) or 36) * 2) % 37
        if i == 15:
            check1 = f"{digits}{ascii_uppercase}"[(37 - adjusted_product) % 36]
    return check1, f"{digits}{ascii_uppercase}"[(37 - adjusted_product) % 36]
