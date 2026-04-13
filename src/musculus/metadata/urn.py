__all__ = ["URN_SCHEME", "URNMixin", "URN"]

from typing import Self
from urllib.parse import SplitResult, quote, unquote, urlsplit

from ..util.functions import (
    eq_slots,
    hash_slots,
    immutable,
    new_with_fields,
    repr_slots_positional,
)
from ..util.parse import (
    ValidityError,
    WellFormednessError,
)
from ..util.standard import StandardIdentifier
from ..util.uri import case_normalize

#: URI scheme for URN
URN_SCHEME = "urn"


class URNMixin(StandardIdentifier):
    __slots__ = ()

    # Just add an NID to the implementing class,
    nid: str

    # we get these mix-in methods for free
    @property
    def nss(self) -> str:
        """Return the URN Namespace-Specific String (NSS) of this instance in percent-encoded form."""
        return quote(self.collate())

    @classmethod
    def from_urn(cls, urn: URN | str, /) -> Self:
        """Constructs an instance of the identifier based on the structured URN."""
        urn = URN.from_urn(urn)
        if urn.nid != cls.nid.casefold():
            raise ValidityError(f"Namespace ID of URN is not {cls.nid!r}: {urn!r}")
        return cls.parse(unquote(urn.nss))

    def to_urn(self) -> URN:
        """Returns a URN from the NID and NSS, percent-encoding them in UTF-8 them in the process.

        NOTE: URN's and their string manifestations are usually unsuitable for use as lexicographic sort keys.
        """
        return URN(self.nid, self.nss)


@immutable
class URN(URNMixin, StandardIdentifier):
    __slots__ = ("nid", "nss")

    #: Positional pattern matching arguments
    #:
    #: :meta public:
    __match_args__ = ("nid", "nss")

    #: Returns the normalized assigned name part of the URN.
    #: RFC 8141 Section 3 URN-equivalence case normalization:
    #: 1. the URI scheme "urn", by conversion to lower case
    #: 2. the NID, by conversion to lower case
    #: 3. any percent-encoded characters in the NSS (that is, all character
    #: triplets that match the <pct-encoding> production found in
    #: Section 2.1 of the base URI specification [RFC3986]), by
    #: conversion to upper case for the digits A-F.

    #: This normalized assigned name is a valid URN string by itself,
    #: and is suitable for use in URN equivalence tests as specified in RFC 8141.

    nid: str
    nss: str

    def __new__(cls, nid: str, nss: str) -> Self:
        if not nid.isascii():
            raise WellFormednessError(f"NID in URN must be ASCII: {nid!r}")
        if not 2 <= len(nid) <= 32:
            raise WellFormednessError(
                f"NID in URN must be between 2 and 32 characters: {nid!r}"
            )
        if (
            not all(c.isalnum() or c == "-" for c in nid)
            or not nid[0].isalnum()
            or not nid[-1].isalnum()
        ):
            raise WellFormednessError(f"Unrecognized character in URN NID: {nid!r}")
        nid = nid.casefold()
        if not nss:
            raise WellFormednessError(f"NSS in URN must not be empty")
        if not nss.isascii():
            raise WellFormednessError(
                f"NSS in URN must be ASCII or it needs to be percent-encoded: {nss!r}"
            )
        if nss[0] == "/":
            raise WellFormednessError(f"NSS in URN must not start with unescaped slash")
        # URNs with percent-encode are considered different. We don't apply any decode here.
        nss = case_normalize(nss, decode=False, enforce_pchars=True, allow_slash=True)
        return new_with_fields(cls, nid=nid, nss=nss)

    __eq__ = eq_slots
    __repr__ = repr_slots_positional
    __hash__ = hash_slots

    def __str__(self) -> str:
        return f"{URN_SCHEME}:{self.nid}:{self.nss}"

    @classmethod
    def parse(cls, source: str | SplitResult, /):
        if isinstance(source, str):
            source = urlsplit(source)
        if source.scheme != URN_SCHEME:
            raise WellFormednessError(f"Wrong URN scheme: {source.scheme!r}")
        if source.netloc:
            raise WellFormednessError(f"URN must not have a netloc: {source.netloc!r}")
        nid, colon, nss = source.path.partition(":")
        return cls(nid, nss)

    collate = presentation = __str__

    @classmethod
    def from_urn(cls, urn: Self | str, /) -> Self:
        if isinstance(urn, str):
            return cls.parse(urn)
        return urn

    def to_urn(self) -> Self:
        return self
