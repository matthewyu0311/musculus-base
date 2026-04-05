from collections.abc import Sequence
from typing import Final, Self

from ..util.functions import immutable
from ..util.parse import (
    CheckDigitError,
    WellFormednessError,
    mod11_check_digit,
    remove_ascii_spaces,
)
from ..util.standard import (
    NumericStandardIdentifier,
    PathResolver,
    PathResolverURIMixin,
)
from .ean13 import EAN13Mixin, parse_ean13
from .urn import URN_SCHEME, URNMixin

MIN_ISSN_EAN13: Final[int] = 977_0000_000_00
MAX_ISSN_EAN13: Final[int] = 977_9999_999_99
MAX_ISSN: Final[int] = 9999_999
JOURNALLAND: Final[str] = "977"


@immutable
class ISSN(EAN13Mixin, PathResolverURIMixin, URNMixin, NumericStandardIdentifier):
    """
    This class implements ISSN.
    The number format is special, and can be converted to EAN13.
    ISSN provides a resolution service.
    ISSN is compatible with URN with Namespace ID "issn".
    """

    # ISSN has no internal structure and the hyphen affords no purpose
    # other than to improve readability.
    # ISSN Manual Section 2.1:
    # An ISSN consists of eight digits.
    # These are the Arabic numerals 0 to 9, except that an upper case X can
    # sometimes occur in the final position as a check digit.

    __slots__ = ()

    RESOLVER_BASES: Sequence[PathResolver] = (
        PathResolver.of_prefix("https://portal.issn.org/resource/ISSN/"),
        PathResolver.of_prefix("https://portal.issn.org/resource/ISSN-L/"),
        PathResolver.of_prefix("https://urn.issn.org/", escape=False),
        PathResolver.of_prefix("http://portal.issn.org/resource/ISSN/"),
        PathResolver.of_prefix("http://portal.issn.org/resource/ISSN-L/"),
        PathResolver.of_prefix("http://urn.issn.org/", escape=False),
    )

    nid: Final[str] = "issn"
    EAN13_RANGES: Final[Sequence[range]] = (range(MIN_ISSN_EAN13, MAX_ISSN_EAN13 + 1),)

    @property
    def check_digit(self) -> str:
        """The ISSN check digit, mod 11.
        NOTE: EAN13 check digit (mod 10) and ISSN check digit are different.
        """
        return mod11_check_digit(self.number)

    # Unlike other identifiers, ISSN URN requires the hyphen in th NSS
    @property
    def nss(self) -> str:
        return str(self)

    def __new__(cls, number: int, /):
        if not 0 <= number <= MAX_ISSN:
            raise WellFormednessError(f"ISSN out of range: {number!r}")
        return NumericStandardIdentifier.__new__(cls, number)

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(f"ISSN not in ASCII: {source!r}")
        s = source.casefold()
        if "issn.org" in s:
            return cls.from_resolver_uri(source)
        s = remove_ascii_spaces(
            s.removeprefix(f"{URN_SCHEME}:")
            .removeprefix(cls.nid)
            .removeprefix("-l")
            .removeprefix(":")
            .replace("-", "")
        )
        match len(s):
            case 8:
                number = int(s[:-1])
                cd = mod11_check_digit(number)
                if s[-1] != cd.casefold():
                    raise CheckDigitError(
                        f"Invalid ISSN check digit: expected {cd!r}, got {s[-1]!r}"
                    )
            case 13:
                # https://www.issn.org/understanding-the-issn/issn-uses/identification-with-the-ean-13-barcode/
                # 977-AAAAAAA-BB-C
                # Where A is the ISSN (without the check digit), B is publisher-specific info
                # C is the EAN-13 check digit
                if not s.startswith(JOURNALLAND):
                    raise WellFormednessError(
                        f"EAN-13 ISSN does not start with {JOURNALLAND}: {s!r}"
                    )
                ean = parse_ean13(s)
                number = (ean - MIN_ISSN_EAN13) // 100
            case n:
                raise WellFormednessError(f"Malformed ISSN of length {n}: {s!r}")
        return cls(number)

    def __str__(self) -> str:
        """Returns the digits with the hyphen between the fourth and fifth digits,
        as ISSN numbers commonly appear on print media."""
        c = self.collate()
        return f"{c[0:4]}-{c[4:8]}"

    def collate(self) -> str:
        """Returns the most concise form of ISSN with 8 digits."""
        # cd =
        return f"{self.number:07d}{self.check_digit}"

    def presentation(self) -> str:
        # ISSN Manual Section 2.1 Construction of ISSN:
        # "[... A] distinction must be preserved in the form of presentation when written or
        # printed. An ISSN is, therefore, preceded by these letters, and appears as two groups of four digits,
        # separated by a hyphen."

        return f"ISSN {self}"
