# SPDX-License-Identifier: MIT
__all__ = [
    "StandardIdentifier",
    "NumericStandardIdentifier",
    "ResolverURIMixin",
    "PathResolverURIMixin",
]
from abc import abstractmethod
from collections.abc import Sequence
from typing import ClassVar, Literal, Self, cast
from urllib.parse import SplitResult

from ..util.uri import PathResolver
from .functions import (
    SlottedImmutableMixin,
    make_compare_fns,
    new_with_fields,
)
from .parse import (
    Parseable,
    ValidityError,
)


class StandardIdentifier(Parseable):
    """
    Base class for identifiers that are implementations of certain standards,
    such as DOI, ISBN, and ISSN.
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def parse(cls, source: str, /) -> Self:
        """Parses an identifier in string form.
        Implementing classes may also accept other types such as bytes and int where appropriate.

        NOTE: the string may be in many formats (such as presentation, collated, URN or URI)
        with varying degrees of case-folding and normalization.
        Implementations must accept all variations as allowed by specification.

        In particular, implementations must accept the results of `str()`, `collate()`,
        `presentation()`.

        Raises ValueError if the input cannot be parsed with respect to specification.
        """
        ...

    @abstractmethod
    def collate(self) -> str:
        """Returns a form suitable for use as "naive" lexicographic comparison within the identifier scheme,
        collated according to specification and without prefixes, optional delimiters or parts.
        ISSN: 2070-1721 should return "20701721".
        doi: 10.1234/aBc should return "10.1234/ABC".
        """
        ...

    @abstractmethod
    def presentation(self) -> str:
        """Returns a human-readable form suitable for presentation in print or text,
        case- and delimiter-preserving where applicable.
        Specifications usually prescribe their own requirements for including identifiers in text and print,
        usually with scheme prefixes such as "ISSN: 2070-1721" and "doi: 10.1234/aBc".

        NOTE: `__str__()` should be used to obtain the "original" form.
        """
        ...

    @abstractmethod
    def __str__(self) -> str:
        """Returns the "original" form of the identifier, case- and delimiter-preserving where applicable.
        Scheme prefix such as "ISSN: " should not be used, unless explicitly required by specification.
        ISSN: 2070-1721 should return "2070-1721".
        doi: 10.1234/aBc should return "10.1234/aBc".

        NOTE: `presentation()` should be used to obtain the human-readable form for inclusion in text.
        """
        ...

    # """For comparison to have meaningful semantics, either identifier object must be an instance of a nominal subtype
    # of the other's type, i.e. `isinstance(other, self.__class__) or isinstance(self, other.__class__)`
    # This ensures that identifiers do not compare equal across disparate schemes,
    # even if they may have the same collated representation.

    # Issues such as normalization such as casefolding and delimiter removal are handled by `collate()`.
    # """
    _, _, __eq__, _, _, __hash__ = make_compare_fns(
        # We have to use dot notation for virtual method dispatch
        lambda s: cast(StandardIdentifier, s).collate()
    )


class NumericStandardIdentifier(SlottedImmutableMixin, StandardIdentifier):
    """A partial implementation of StandardIdentifier based on a number."""

    __slots__ = __match_args__ = ("number",)
    number: int

    def __new__(cls, number: int, /):
        return new_with_fields(NumericStandardIdentifier, cls, number=number)

    def __index__(self) -> int:
        return self.number

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.number})"

    __int__ = __index__

    def __bool__(self) -> Literal[True]:
        """Numeric identifiers always evaluate as true in boolean contexts."""
        return True


class ResolverURIMixin:
    __slots__ = ()

    @abstractmethod
    def collate(self) -> str: ...

    @classmethod
    @abstractmethod
    def parse(cls, source: str, /) -> Self: ...

    @classmethod
    @abstractmethod
    def from_resolver_uri(cls, url: SplitResult | str, /) -> Self: ...

    @abstractmethod
    def to_resolver_uri(self) -> SplitResult: ...


class PathResolverURIMixin(ResolverURIMixin):
    # Implementation based on a prefix string
    __slots__ = ()

    # In any case, the first of the RESOLVER_BASES is the preferred one
    RESOLVER_BASES: ClassVar[Sequence[PathResolver]]

    @classmethod
    def from_resolver_uri(cls, uri: SplitResult | str, /) -> Self:
        from ..metadata.urn import URNMixin

        for resolver in cls.RESOLVER_BASES:
            try:
                result = resolver.resolve(uri)
                if result.casefold().startswith("urn:") and issubclass(cls, URNMixin):
                    return cls.from_urn(result)
                return cls.parse(result)
            except ValueError:
                continue
        raise ValidityError(f"No matching base resolver URI found: {str(uri)!r}")

    def to_resolver_uri(self) -> SplitResult:
        return self.RESOLVER_BASES[0].to_resolver_uri(self.collate())
