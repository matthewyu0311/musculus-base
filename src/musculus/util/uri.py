# SPDX-License-Identifier: MIT
"""This module provides supporting utility for URI processing that are of use to other modules.
The functionality is based on RFC 3986.
This is not intended to be a general-purpose URI library; packages such as data-url, urlstd
and uts46 are much more suitable for general URI processing.
"""

__all__ = [
    "CHARS_TSPECIALS",
    "UNRESERVED",
    "SET_UNRESERVED",
    "SUB_DELIMS",
    "SET_SUB_DELIMS",
    "SET_PCHARS",
    "PCT_ENCODED",
    "PCHAR",
    "CHARS_PCHARS",
    "R_COMPONENT",
    "Q_COMPONENT",
    "F_COMPONENT",
    "URI_SCHEME_PATTERN",
    "DEFAULT_PORTS",
    "case_normalize_iter",
    "case_normalize",
    "DissectDict",
    "dissect_uri",
    "recompose_uri",
    "remove_trailing_slash",
]

import re
from collections import deque
from collections.abc import Iterable, Sequence
from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from string import ascii_letters, digits, hexdigits
from tracemalloc import start
from typing import TypedDict
from urllib.parse import SplitResult, unquote, urlsplit

from .parse import (
    ValidityError,
    WellFormednessError,
)

# Productions from RFC 3986 and RFC 8141
# ALPHANUM =  ALPHA / DIGIT
# pct-encoded = "%" HEXDIG HEXDIG
# unreserved = ALPHA / DIGIT / "-" / "." / "_" / "˜"
# sub-delims = "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="
#
# pchar = unreserved / pct-encoded / sub-delims / ":" / "@"
#       => ALPHA / DIGIT / "-._~" / "!$&'()*+,;=" / ":" / "@" / everything else needs to be pct-encoded
# namestring = assigned-name
#              [ rq-components ]
#              [ "#" f-component ]
#  assigned-name = "urn" ":" NID ":" NSS
#  NID = (alphanum) 0*30(ldh) (alphanum)
#  ldh = alphanum / "-"
#  NSS = pchar *(pchar / "/")
#  rq-components = [ "?+" r-component ]
#                  [ "?=" q-component ]
#  r-component = pchar *( pchar / "/" / "?" )
#  q-component = pchar *( pchar / "/" / "?" )
#  f-component = fragment
# fragment = *( pchar / "/" / "?" )


CHARS_TSPECIALS = R"()<>@,;:\"/[]?="
UNRESERVED = r"[0-9A-Za-z.~_-]"
SET_UNRESERVED = frozenset(ascii_letters + digits + ".~_-")
SUB_DELIMS = r"[!$&'()*+,;=]"
SET_SUB_DELIMS = frozenset(R"!$&'()*+,;=")
SET_PCHARS = SET_UNRESERVED | SET_SUB_DELIMS | frozenset(":@")
PCT_ENCODED = r"%[0-9A-Fa-f]{2}"
PCHAR = rf"(?:[0-9A-Za-z.~_!$&'()*+,;=:@-]|{PCT_ENCODED})"
CHARS_PCHARS = "".join(sorted(SET_PCHARS))

R_COMPONENT = rf"(?P<R_COMPONENT>{PCHAR}(?:{PCHAR}|[?/])*)"
Q_COMPONENT = rf"(?P<Q_COMPONENT>{PCHAR}(?:{PCHAR}|[?/])*)"
F_COMPONENT = rf"(?P<F_COMPONENT>{PCHAR}(?:{PCHAR}|[?/])*)"

URI_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+-.]*", re.ASCII | re.IGNORECASE)


DEFAULT_PORTS = {
    "ftp": 21,
    "file": None,
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}


def case_normalize_iter(
    source: Iterable[str],
    /,
    *,
    casefold: bool = False,
    decode: bool = True,
    enforce_pchars: bool = False,
    allow_slash: bool = True,
) -> Iterable[str]:
    # No default arguments for decode and casefold
    """Iteratively case-normalizes the input.
    This also serves as the implementation of the non-iterative `case_normalize` function.
    """
    it = iter(source)
    for c in it:
        if c == "%":
            try:
                first = next(it)
                second = next(it)
            except StopIteration:
                raise WellFormednessError(f"Source terminated while in percent-escape")
            if first not in hexdigits or second not in hexdigits:
                raise WellFormednessError(
                    f"Unexpected character in percent-escape: %{first}{second}"
                )
            if decode:
                decoded = chr(int(f"{first}{second}", base=16))
            else:
                decoded = None
            if decode and decoded in SET_UNRESERVED:
                # Decoding unreserved octets is conditional
                yield decoded.casefold() if casefold else decoded
            else:
                # Uppercasing hex digits is always applied
                yield "%"
                yield first.upper()
                yield second.upper()
        elif allow_slash and c == "/":
            yield "/"
        elif enforce_pchars and c not in SET_PCHARS:
            raise WellFormednessError(f"Character not in PCHARS: {c!r}")
        else:
            yield c.casefold() if casefold else c


@lru_cache(maxsize=256)
def case_normalize(
    source: str,
    /,
    *,
    casefold: bool = False,
    decode: bool = True,
    enforce_pchars: bool = False,
    allow_slash: bool = True,
) -> str:
    """Normalizes all percent-sequences, which is, to make the hexadecimals all uppercase (`%AB`).
    There are two closely-related but distinct operations:
    - Uppercase %xx hexadecimal digits
    - `decode`: Decode unreserved percent-encoded octets (0-9A-Za-z-.~_)

    Some RFCs specifically require or prohibit these operations.
    For example, URN comparison only allows uppercasing hex digits and prohibits decoding.
    Due to this, URNs are not considered to be subset of URIs.

    - `enforce_pchars` enforces the requirement that all non-escaped characters be one of the PCHARS.

    NOTE: This is an unstructured string operation. URI component syntax equivalence rules
    are NOT applied here.
    """
    return "".join(
        case_normalize_iter(
            source,
            casefold=casefold,
            decode=decode,
            enforce_pchars=enforce_pchars,
            allow_slash=allow_slash,
        )
    )


class DissectDict(TypedDict):
    scheme: str | None
    username: str | None
    password: str | None
    host: str | IPv4Address | IPv6Address | None
    port: int | None
    is_localhost: bool | None
    path: Sequence[str]
    query: str
    fragment: str


def dissect_uri(uri: str | SplitResult, /) -> DissectDict:
    """
    Normalizes and dissects the incoming URI into a TypedDict.
    To normalize URIs:
    1. Split into components
    2. Determine scheme
    4. perform Syntax-Based Normalization (6.2.2) on the path.

    Only non-reserved octets will be percent-decoded.
    """

    # From 2.3:
    #    URIs that differ in the replacement of an unreserved character with
    #    its corresponding percent-encoded US-ASCII octet are equivalent: they
    #    identify the same resource.  However, URI comparison implementations
    #    do not always perform normalization prior to comparison (see Section
    #    6).

    # urllib.parse conspicuously lacks a normalization feature
    # scheme is casefolded to lowercase. No escapes are allowed.
    # URIs by definition have a scheme; relative references don't
    if isinstance(uri, str):
        uri = urlsplit(uri)
    if not uri.scheme:
        # Relative reference cannot generally be normalized (5.2.1)
        scheme = None
    elif URI_SCHEME_PATTERN.fullmatch(uri.scheme):
        # Schemes are casefolded to lowercase and never contain % encodes
        scheme = uri.scheme.casefold()
    else:
        raise WellFormednessError(
            f"URI Scheme must consist of only ASCII letters, digits, plus, minus, and dot: {uri.scheme!r}"
        )
    # Enforce Section 3.3:
    # If a URI contains an authority component, then the path component
    # must either be empty or begin with a slash ("/") character.
    # If a URI does not contain an authority component, then the path cannot begin
    # with two slash characters ("//").
    # In addition, a URI reference (Section 4.1) may be a relative-path reference, in which case the
    # first path segment cannot contain a colon (":") character.
    username = None
    password = None
    host = None
    is_localhost = None
    port = None
    if uri.netloc:
        # The authority component takes the form of userinfo@host:port
        # (deprecated as unsafe in the RFC: username:password@host:port)
        username = uri.username
        password = uri.password
        hostname = uri.hostname
        if hostname:
            if ":" in hostname:
                try:
                    host = IPv6Address(hostname)
                    is_localhost = host.is_loopback
                except ValueError:
                    # IPv6 scoped zone identifiers are not supported in RFC 3986 (and WHATWG)
                    # but are supported in RFC 6874
                    raise WellFormednessError(
                        f"Cannot parse IPv6 address: {hostname!r}"
                    )
            else:
                try:
                    host = IPv4Address(hostname)
                    is_localhost = host.is_loopback
                except ValueError:
                    # not IPv4 decimal octets
                    host = "".join(case_normalize(hostname, casefold=True, decode=True))
                    is_localhost = host == "localhost"
        try:
            port = uri.port
        except ValueError as ve:
            # While the ABNF permits port numbers outside 0..65535, other specs don't
            raise ValidityError("Port number out of range") from ve
        # WHATWG default port logic: if the default port of the scheme
        if scheme is not None:
            default_port = DEFAULT_PORTS.get(scheme, None)
            if port == default_port:
                port = None
        if uri.path and uri.path[0] != "/":
            raise WellFormednessError(
                f"URI with an authority component must have path begin with a slash: {uri!r}"
            )
    else:
        # No netloc, no host string
        if uri.path and uri.path.startswith("//"):
            raise WellFormednessError(
                f"URI without authority component must not have path beginning with two slashes: {uri!r}"
            )

    if not uri.path:
        path = []
    elif uri.scheme:
        # Non-relative reference
        path = _remove_dot_segments(uri.path.split("/"))
    else:
        # Relative reference paths cannot undergo remove_dot_segments
        path = uri.path.split("/")
    return {
        "scheme": scheme,
        "username": username or None,
        "password": password or None,
        "host": host,
        "is_localhost": is_localhost,
        "port": port,
        "path": path,
        "query": case_normalize(
            uri.query
        ),  # Due to urlsplit we no longer know if query is undefined (rather than empty)
        "fragment": case_normalize(uri.fragment),
    }


def _merge_path(base_path: Sequence[str], reference_path: Sequence[str]) -> list[str]:
    """Performs the "merge path" operation, taking a base path and a reference path as inputs."""
    # If the base URI has an empty path, or if the reference path starts with "/", use the reference's
    if not base_path or (reference_path and not reference_path[0]):
        return list(reference_path)
    # Otherwise, cut the last part of the base path and append the reference's
    # We have to convert base_path into a list because other sequences don't allow slicing
    return [*list(base_path)[:-1], *reference_path]


def _remove_dot_segments(segments: Sequence[str], /) -> Sequence[str]:
    """Performs the `remove_dot_segments` routine in RFC 3986.

    The input and output segments shall be the result of splitting on "/" delimiter:
    `"/".join(remove_dot_segments(path.split("/")))`
    """
    output_segments = deque()
    if not segments:
        return output_segments
    input_segments = deque(segments)

    i = 0
    absolute_path = False
    while True:
        try:
            segm = input_segments.popleft()
        except LookupError:
            break
        match segm:
            case ".":
                if not input_segments:
                    # NOTE: "a/b/c/g" + "." should result in "a/b/c/" (has trailing slash)
                    # Textually, "." should remove the slash AFTER the dot, not before
                    output_segments.append("")
            case "..":
                try:
                    output_segments.pop()
                except IndexError:
                    pass
                if not input_segments:
                    # NOTE: "a/b/c/g" + ".." should result in "a/b/" (has trailing slash)
                    # Textually, "." should remove the slash AFTER the dot, not before
                    output_segments.append("")
            case "" if i == 0:
                absolute_path = True
            case c:
                output_segments.append(c)
        i += 1
    if absolute_path:
        output_segments.appendleft("")
    return list(output_segments)


def _transform_reference(
    base: SplitResult | DissectDict,
    reference: SplitResult | DissectDict,
    *,
    strict: bool = False,
) -> DissectDict:
    """Implements RFC 3986 Section 5.2.2 Transform References"""
    if isinstance(base, dict):
        bd = base
    else:
        bd = dissect_uri(base)
    if isinstance(reference, dict):
        rd = reference
    else:
        rd = dissect_uri(reference)

    bds = bd["scheme"]
    rds = rd["scheme"]
    if not strict and rds == bds:
        rds = None
    elif rds is not None:
        # Since the reference is absolute, remove_dot_segments has already been performed
        return rd

    if rd["host"] is not None:
        # Relative reference has no scheme, set it to that of the base
        rd["scheme"] = bds
        # Everything else has been copied, we only have to perform remove_dot_segments
        rd["path"] = _remove_dot_segments(rd["path"])
        return rd

    # RR has no host, use that of the base
    rdp = rd["path"]
    bdp = bd["path"]
    if rdp:
        bd["path"] = _remove_dot_segments(_merge_path(bdp, rdp))
        bd["query"] = rd["query"]
    else:
        # RR has no path, use that of the base
        bd["path"] = _remove_dot_segments(bdp)
        # RR may still have a query though, which we use
        bd["query"] = rd["query"] or bd["query"]
    # We always use the RR's fragment
    bd["fragment"] = rd["fragment"]
    return bd


def recompose_uri(d: DissectDict, /) -> SplitResult:
    """Recomposes a DissectDict back into a URI."""
    scheme = d["scheme"] or ""
    hostl: list[str] = []
    host = d["host"]
    if host is not None:
        username = d["username"]
        if username:
            hostl.append(username)
            password = d["password"]
            if password:
                hostl.append(f":{password}")
            hostl.append("@")
        match host:
            case IPv6Address():
                hostl.append(f"[{str(host)}]")
            case _:
                hostl.append(str(host))
        port = d["port"]
        if port is not None and DEFAULT_PORTS.get(scheme, None) != port:
            hostl.append(f":{port}")
    path = "/".join(d["path"])
    query = d["query"]
    fragment = d["fragment"]
    return SplitResult(scheme, "".join(hostl), path, query, fragment)


def remove_trailing_slash(path: Sequence[str], /) -> Sequence[str]:
    output = []
    for p in reversed(path):
        if not p and not output:
            continue
        output.append(p)
    output.reverse()
    return output
