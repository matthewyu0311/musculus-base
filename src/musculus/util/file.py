"""This module contains several functions for working with file- and path-related strings."""

from email.policy import HTTP as HTTP_POLICY
from email.message import Message
import os
from functools import lru_cache, partial
from mimetypes import MimeTypes, guess_file_type, guess_type
from collections.abc import Callable, Iterable, Mapping
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import ClassVar, Self
from urllib.parse import SplitResult

from .functions import eq_slots, new_with_fields, safe_splat

from .parse import ASCII_ALNUM, make_wellformed, split_escape

# We're not doing os.path's work here:
# If environment variable expansion is desired, use os.path.expandvars before splitting
split_windoows_paths: Callable[[str], Iterable[PureWindowsPath]] = partial(
    split_escape,
    separator=";",
    escape=None,
    lstrip=True,
    rstrip=True,
    keep_empty=True,
    output_fn=PureWindowsPath,
)


split_posix_paths: Callable[[str], Iterable[PurePosixPath]] = partial(
    split_escape,
    separator=":",
    escape=None,
    lstrip=True,
    rstrip=True,
    keep_empty=False,
    output_fn=PurePosixPath,
)


def join_paths(
    paths: Iterable[PurePath | str],
    /,
    *,
    separator: str = os.pathsep,
    escape: str | None = None,
) -> str:
    output = []
    replacement = (escape or "") + separator
    for path in paths:
        s = str(path).replace(separator, replacement)
        output.append(s)
    return separator.join(output)


# From RFC 6838
restricted_name_first = ASCII_ALNUM
restricted_name_chars = ASCII_ALNUM + "!#$&-^_+."

_CASE_INSENSITIVE_PARAMS = {"charset"}


class MediaType:
    __slots__ = ("top_level_type", "subtype", "_parameters")
    top_level_type: str
    subtype: str
    _parameters: Mapping[str, str]

    def __new__(cls, top_level_type: str, subtype: str, /, **params):
        top_level_type = make_wellformed(
            top_level_type,
            "Media top-level type",
            ascii_only=True,
            casefold=True,
            strip=True,
            length=(1, 127),
            first_chars=restricted_name_first,
            continue_chars=restricted_name_chars,
            intern=True,
        )
        subtype = make_wellformed(
            subtype,
            "Media subtype",
            ascii_only=True,
            casefold=True,
            strip=True,
            length=(1, 127),
            no_whitespaces=True,
            first_chars=restricted_name_first,
            continue_chars=restricted_name_chars,
            intern=True,
        )
        p = {}
        for k, v in params.items():
            # RFC 6838 4.3.  Parameter Requirements:
            #  Parameter names have the syntax as media type names and values
            k = make_wellformed(
                k,
                "Media parameter name",
                ascii_only=True,
                casefold=True,
                strip=True,
                length=(1, 127),
                no_whitespaces=True,
                first_chars=restricted_name_first,
                continue_chars=restricted_name_chars,
            )
            if k in p:
                raise KeyError(f"Duplicate parameter name: {k!r}")
            if k in _CASE_INSENSITIVE_PARAMS:
                v = v.casefold()
            p[k] = v

        return new_with_fields(
            cls,
            top_level_type=top_level_type,
            subtype=subtype,
            _parameters={k: p[k] for k in sorted(p.keys())},
        )

    def __repr__(self) -> str:
        s = [f"{self.top_level_type!r}", f"{self.subtype!r}"]
        if self._parameters:
            s.append(safe_splat(self._parameters))
        return f"{self.__class__.__qualname__}({', '.join(s)})"

    __eq__ = eq_slots

    def __hash__(self) -> int:
        return hash(
            (
                self.top_level_type,
                self.subtype,
                frozenset(map(tuple, self._parameters.items())),
            )
        )

    def __str__(self) -> str:
        simple = f"{self.top_level_type}/{self.subtype}"
        if not self._parameters:
            return simple
        msg = Message(HTTP_POLICY)
        msg.set_type(simple)
        for k, v in self._parameters.items():
            msg.set_param(k, v)
        return msg["content-type"]

    def __getitem__(self, key):
        return self._parameters[key]

    @classmethod
    @lru_cache
    def parse(cls, source: str, /) -> Self:
        msg = Message(HTTP_POLICY)
        msg.set_type(source)
        top_level_type = msg.get_content_maintype()
        subtype = msg.get_content_subtype()
        params = msg.get_params()
        assert params is not None
        return cls(top_level_type, subtype, **dict(params[1:]))
    
    @classmethod
    def guess_file_type(
        cls, 
        path: PurePath | str,
        /,
        *,
        db: MimeTypes | None = None,
        strict: bool = False
    ) -> Self:
        """Guesses the media type from the file path. Returns `None` if no such information may be inferred.
        The `MimeTypes` database can be specified for dependency injection. If `None`, uses the default database.
        See the documentation on `mimetypes` for strict mode. 
        """
        if db is not None:
            result, _encoding = db.guess_file_type(path, strict=strict)
        else:
            result, _encoding = guess_file_type(path, strict=strict)
        if result is None:
            return cls.APPLICATION_OCTET_STREAM
        return cls.parse(result)

    @classmethod
    def guess_uri_type(
        cls, 
        uri: str | SplitResult,
        /,
        *,
        db: MimeTypes | None = None,
        strict: bool = False
    ) -> Self:
        """Guesses the media type from the URI.
        Returns `None` if no such information may be inferred.
        The `MimeTypes` database can be specified for dependency injection. If `None`, uses the default database.
        See the documentation on `mimetypes` for strict mode.
        """
        if isinstance(uri, PurePath):
            # guess_type's acceptance of file paths is deprecated
            raise TypeError("Path objects are not supported. Use guess_file_type instead.")
        if isinstance(uri, SplitResult):
            uri = uri.geturl()
        if db is not None:
            result, _encoding = db.guess_type(uri, strict=strict)
        else:
            result, _encoding = guess_type(uri, strict=strict)
        if result is None:
            return cls.APPLICATION_OCTET_STREAM
        return cls.parse(result)
    
    APPLICATION_OCTET_STREAM: ClassVar[Self]
    TEXT_PLAIN: ClassVar[Self]
    TEXT_PLAIN_US_ASCII: ClassVar[Self]
    TEXT_PLAIN_UTF8: ClassVar[Self]
    TEXT_HTML: ClassVar[Self]
    TEXT_MARKDOWN: ClassVar[Self]
    IMAGE_GIF: ClassVar[Self]
    IMAGE_JPEG: ClassVar[Self]
    IMAGE_PNG: ClassVar[Self]
    APPLICATION_PDF: ClassVar[Self]
    APPLICATION_ZIP: ClassVar[Self]
    APPLICATION_GZIP: ClassVar[Self]

# Commonly used media types
MediaType.APPLICATION_OCTET_STREAM = MediaType.parse("application/octet-stream")
MediaType.TEXT_PLAIN = MediaType.parse("text/plain")
MediaType.TEXT_PLAIN_US_ASCII = MediaType.parse('text/plain; charset="us-ascii"')
MediaType.TEXT_PLAIN_UTF8 = MediaType.parse('text/plain; charset="utf-8"')
MediaType.TEXT_HTML = MediaType.parse("text/html")
MediaType.TEXT_MARKDOWN = MediaType.parse("text/markdown")
MediaType.IMAGE_GIF = MediaType.parse("image/gif")
MediaType.IMAGE_JPEG = MediaType.parse("image/jpeg")
MediaType.IMAGE_PNG = MediaType.parse("image/png")
MediaType.APPLICATION_PDF = MediaType.parse("application/pdf")
MediaType.APPLICATION_ZIP = MediaType.parse("application/zip")
MediaType.APPLICATION_GZIP = MediaType.parse("application/gzip")
