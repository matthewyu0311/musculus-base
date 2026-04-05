# SPDX-License-Identifier: MIT

import re
from collections.abc import Sequence
from typing import Final, Self
from urllib.parse import SplitResult, quote, unquote

from ..util.functions import (
    immutable,
    make_compare_fns,
    new_with_fields,
    repr_slots_positional,
)
from ..util.parse import ValidityError, WellFormednessError, ascii_casefold
from ..util.standard import PathResolver, PathResolverURIMixin, StandardIdentifier
from .urn import URN, URNMixin

DOI_PATTERN = re.compile(
    r"((?P<urn>urn:doi:)|doi:)?(?P<prefix>[0-9]+(.[0-9]+)*)(?(urn)[\/\:]|\/)(?P<suffix>[^\/][\s\S]*)",
    re.IGNORECASE,
)


@immutable
class DOI(URNMixin, PathResolverURIMixin, StandardIdentifier):
    """
    Digital Object Identifier (DOI) is composed of a prefix and suffix, both strings.

    The DOI syntax shall be made up of a DOI prefix and a DOI suffix separated by a forward slash.
    At resolution time the DOI is a Unicode opaque string, which should be encoded in UTF-8.
    DOI can be encoded into URN with NID "doi". Special characters need percent-encoding.
    DOI provides a global online resolver service at https://doi.org/
    """

    #: Positional pattern matching arguments
    __slots__ = ("prefix", "suffix")
    prefix: str
    suffix: str

    nid: Final[str] = "doi"

    RESOLVER_BASES: Sequence[PathResolver] = (
        PathResolver.of_prefix("https://doi.org/"),
        PathResolver.of_prefix("https://dx.doi.org/"),
        PathResolver.of_prefix("http://doi.org/"),
        PathResolver.of_prefix("http://dx.doi.org/"),
    )

    __match_args__ = ("prefix", "suffix")

    def __new__(cls, prefix: str, suffix: str) -> Self:
        # 3.2.1
        # GENERAL CHARACTERISTICS OF THE DOI SYNTAX
        # The DOI syntax shall be made up of a DOI prefix and a DOI suffix separated by a forward
        # slash.
        # There is no defined limit on the length of the DOI name, or of the DOI prefix or DOI suffix.
        # The DOI name is case-insensitive and can incorporate any printable characters from the legal
        #  graphic characters of Unicode.

        if not prefix.isprintable():
            raise WellFormednessError(
                "Non-printable characters in prefix (DOI Handbook 3.2.1)"
            )

        if not all(s in "0123456789." for s in prefix):
            raise WellFormednessError("Non-numeric prefix (DOI Handbook 3.2.2)")
        directory_indicator, dot, registrant_code = prefix.partition(".")
        if not directory_indicator:
            raise ValidityError(
                "Missing directory indicator in prefix (DOI Handbook 3.2.2)"
            )
        elif directory_indicator == "10":
            if not registrant_code:
                raise ValidityError(
                    'Missing registrant code for directory indicator "10". (DOI Handbook 3.2.2)'
                )

        if not suffix:
            raise WellFormednessError("Empty suffix")
        elif not suffix.isprintable():
            raise WellFormednessError(
                "Non-printable characters in suffix (DOI Handbook 3.2.1)"
            )

        # Don't check the well-formedness of the suffix:
        #   "Neither the Handle System nor DOI system policies, nor any web use currently imaginable,
        #   impose any constraints on the suffix, outside of encoding"
        return new_with_fields(cls, prefix=prefix, suffix=suffix)

    def collate(self) -> str:
        """Returns an ASCII-casefolded string of prefix "/" suffix, suitable for use as dictionary keys."""
        return f"{self.prefix}/{ascii_casefold(self.suffix, upper=True)}"

    def __str__(self) -> str:
        """Returns a case-preserved string of the DOI name.
        This string has the form of case-preserved prefix, followed by "/", followed by case-preserved suffix.
        See other methods for various forms of presentation including screen / print and URI / URN.
        """
        return f"{self.prefix}/{self.suffix}"

    __lt__, __le__, __eq__, __ge__, __gt__, __hash__ = make_compare_fns(
        lambda self: (self.prefix, ascii_casefold(self.suffix, upper=True))
    )
    __repr__ = repr_slots_positional

    @property
    def nss(self) -> str:
        """Returns the Namespace-Specific String of the URN that would be formed from this DOI.
        NOTE: The 2023 version of the namespace registration allows the use of slash.
        Example: `10.123/abc`"""
        prefix, suffix = self.encode()
        return f"{prefix}/{suffix}"

    @classmethod
    def from_urn(cls, urn: URN | str, /) -> Self:
        """Processes URN of the form `urn:doi:10.123/abcde` into `doi:10.123/abcde`."""
        urn = URN.from_urn(urn)
        if urn.nid.casefold() != cls.nid.casefold():
            raise ValidityError(f"Namespace ID of URN is not {cls.nid}: {urn}")
        # NOTE: Both : and / are acceptable in URN. Partition on the first one.
        try:
            colon_index = urn.nss.index(":")
        except ValueError:
            # No colon, use slash
            prefix, _, suffix = urn.nss.partition("/")
        else:
            try:
                slash_index = urn.nss.index("/")
            except ValueError:
                # No slash, use colon
                prefix, _, suffix = urn.nss.partition(":")
            else:
                # We have both slash and colon
                which = min(colon_index, slash_index)
                prefix = urn.nss[0:which]
                suffix = urn.nss[which + 1 :]
        return cls(
            unquote(prefix, encoding="utf-8", errors="strict"),
            unquote(suffix, encoding="utf-8", errors="strict"),
        )

    def presentation(self) -> str:
        """Returns a presentation string for this DOI, along the rules described in
        DOI Handbook 2.6.1 "Screen and print presentation".
        This string has the form of "doi:", followed by the prefix, followed by "/",
        followed by suffix.
        """
        return f"doi:{self}"

    def encode(self, *, normalize: bool = False) -> tuple[str, str]:
        """Return a 2-tuple of strings corresponding to the "encoded" form of prefix and suffix respectively,
        along the rules described in DOI Handbook 2.5.

        :param normalize: If true, case in prefix and suffix is casefolded to the ASCII-casefolded uppercase form.

        NOTE on forward slashes: DOI Handbook Section 2.5.2.4 recommends that one of the slashes in the
        special forms `/./` `/../` be encoded as `%2F`.
        This method encodes the latter slash in `//`, `/./`, and `/../`
        """

        if normalize:
            p = ascii_casefold(self.prefix, upper=True)
            s = ascii_casefold(self.suffix, upper=True)
        else:
            p = self.prefix
            s = self.suffix
        encoded_suffix = quote(s, safe="/")
        encoded_suffix = encoded_suffix.replace("//", "/%2F")
        encoded_suffix = encoded_suffix.replace("/./", "/.%2F")
        encoded_suffix = encoded_suffix.replace("/../", "/..%2F")
        return quote(p, safe=""), encoded_suffix

    def to_resolver_uri(self) -> SplitResult:
        prefix, suffix = self.encode()
        return self.RESOLVER_BASES[0].to_resolver_uri(
            f"{prefix}/{suffix}", no_quote=True
        )

    @classmethod
    def parse(cls, source: str, /) -> Self:
        """
        Parses DOI string representation in the "xxxx/yyyy" or "doi:xxxx/yyyy" form.
        It also handles the "urn:doi:xxxx/yyyy" andd "urn:doi:xxxx:yyyy" forms.
        Othewise, assume that source has been already unescaped.
        """

        # from_resolver_uri already unquotes the "xxxx/yyyy" before calling parse
        # The problem is that resolvers also accept "https://doi.org/urn:doi:xxxx:yyyy"
        # and "https://doi.org/urn:doi:10.123:456ABC%2Fzyz"

        m = DOI_PATTERN.fullmatch(source)
        if m is None:
            raise WellFormednessError(f"Source cannot be parsed as DOI: {source!r}")
        is_urn = m.group("urn") is not None
        prefix = m.group("prefix")
        suffix = m.group("suffix")
        if is_urn:
            prefix = unquote(prefix)
            suffix = unquote(suffix)
        return cls(prefix, suffix)
