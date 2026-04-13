# SPDX-License-Identifier: MIT
__all__ = [
    "StandardIdentifier",
    "NumericStandardIdentifier",
    "ResolverURIMixin",
    "PathResolver",
    "PathResolverURIMixin",
]
from abc import abstractmethod
from collections.abc import Sequence
from ipaddress import IPv4Address, IPv6Address
from typing import ClassVar, Literal, Self, cast
from urllib.parse import SplitResult, quote, unquote, urlsplit

from .functions import (
    SlottedImmutableMixin,
    eq_slots,
    hash_slots,
    make_compare_fns,
    new_with_fields,
    repr_slots,
    seq_endswith,
    seq_startswith,
)
from .parse import (
    Parseable,
    ValidityError,
)
from .uri import (
    DEFAULT_PORTS,
    case_normalize,
    dissect_uri,
    remove_trailing_slash,
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

    __slots__ = ("number",)
    number: int

    __match_args__ = ("number",)

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


# Unlike other classes, this is mutable
class PathResolver:
    __slots__ = (
        "scheme",
        "host",
        "path_start",
        "prefix",
        "suffix",
        "path_end",
        "port",
        "query",
        "escape",
    )
    # All components components should be stored percent-encoded and case-normalized as necessary

    def __init__(
        self,
        scheme: str,
        host: str | IPv4Address | IPv6Address,
        path_start: Sequence[str] = ("",),
        prefix: str = "",
        suffix: str = "",
        path_end: Sequence[str] = (),
        *,
        port: int | None = None,
        query: str = "",
        escape: bool = True,
    ) -> None:
        self.scheme = case_normalize(scheme)
        if isinstance(host, str):
            self.host = case_normalize(host)
        else:
            self.host = host
        if DEFAULT_PORTS.get(scheme, None) == port:
            self.port = None
        else:
            self.port = port
        self.path_start = path_start
        self.prefix = prefix
        self.suffix = suffix
        self.path_end = path_end
        self.query = query
        # Whether to perform percent-escape and unescape across API boundary
        self.escape = escape

    @classmethod
    def of_prefix(cls, uri: str | SplitResult, /, *, escape: bool = True) -> Self:
        if isinstance(uri, str):
            uri = urlsplit(uri)
        if not uri.hostname:
            raise ValueError("No host provided")
        path = uri.path.split("/")
        path = tuple(remove_trailing_slash(path))
        if not path:
            path = ("",)
        return cls(
            uri.scheme,
            uri.hostname,
            path_start=path,
            port=uri.port,
            query=uri.query,
            escape=escape,
        )

    __eq__ = eq_slots
    __repr__ = repr_slots
    __hash__ = hash_slots

    def resolve(
        self, uri: str | SplitResult, /, remove_trailing_slashes: bool = True
    ) -> str:
        """Return a non-unquoted resolved component.
        `remove_end_slashes` specifies if trailing slashes should be removed.
        """
        d = dissect_uri(uri)
        if d["scheme"] != self.scheme:
            raise ValueError(f"Expected scheme {self.scheme!r}, got {d['scheme']!r}")
        if d["host"] != self.host:
            raise ValueError(f"Expected host {self.host!r}, got {d['host']!r}")
        if d["port"] != self.port:
            raise ValueError(f"Expected port {self.port!r}, got {d['port']!r}")

        path_start = self.path_start
        if remove_trailing_slashes:
            components = remove_trailing_slash(d["path"])
            path_end = remove_trailing_slash(self.path_end)
        else:
            components = d["path"]
            path_end = self.path_end
        if not seq_startswith(d["path"], path_start):
            raise ValueError(
                f"Expected path to start with {'/'.join(path_start)!r}, got {'/'.join(d['path'])!r}"
            )
        start = len(path_start)
        if not seq_endswith(components, path_end):
            raise ValueError(
                f"Expected path to end with {'/'.join(path_end)!r}, got {'/'.join(d['path'])!r}"
            )
        end = len(components) - len(path_end)
        if start >= end:
            raise ValueError(f"No component found for path {'/'.join(d['path'])!r}")

        # There may be more than one path component, i.e. end - start > 1
        output = "/".join(components[start:end])
        if not output.startswith(self.prefix):
            raise ValueError(f"Expected prefix {self.prefix}, got {output!r}")
        output = output.removeprefix(self.prefix)
        if not output.endswith(self.suffix):
            raise ValueError(f"Expected suffix {self.suffix}, got {output!r}")
        output = output.removesuffix(self.suffix)
        # We're PathResolver, we don't care if the query is different!
        if self.escape:
            return unquote(output)
        return output

    def to_resolver_uri(self, source: str, /, *, no_quote: bool = False) -> SplitResult:
        if isinstance(self.host, IPv6Address):
            netloc = f"[{self.host}]"
        else:
            netloc = str(self.host)
        if self.port is not None:
            netloc = f"{netloc}:{self.port}"
        if self.escape and not no_quote:
            # We allow the slash to pass through, this is needed for DOI
            source = quote(source)
        x = f"{self.prefix}{source}{self.suffix}"
        components = [*self.path_start, x, *self.path_end]
        path = "/".join(components)
        return SplitResult(
            scheme=self.scheme,
            netloc=netloc,
            path=path,
            query=self.query,
            fragment="",
        )


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
