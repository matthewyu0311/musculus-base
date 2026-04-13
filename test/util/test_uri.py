# SPDX-License-Identifier: MIT

import unittest
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from musculus.util.uri import _remove_dot_segments


class TestURI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global case_normalize, _remove_dot_segments
        from musculus.util.uri import _remove_dot_segments, case_normalize

    def test_case_normalize(self):
        # RFC 3986 2.3;
        #   For consistency, percent-encoded octets in the ranges of ALPHA
        #    (%41-%5A and %61-%7A), DIGIT (%30-%39), hyphen (%2D), period (%2E),
        #    underscore (%5F), or tilde (%7E) should not be created by URI
        #    producers and, when found in a URI, should be decoded to their
        #    corresponding unreserved characters by URI normalizers.
        cases = {
            "ABC%5c%7e": "abc%5C~",
        }
        self.assertEqual(
            case_normalize("HTTP://www.EXAMPLE.com/", casefold=False),
            "HTTP://www.EXAMPLE.com/",
        )
        self.assertEqual(
            case_normalize("HTTP://www.EXAMPLE.com/", casefold=True),
            "http://www.example.com/",
        )
        self.assertEqual(case_normalize("%30", decode=True), "0")
        self.assertEqual(case_normalize("%30", decode=False), "%30")
        self.assertEqual(case_normalize("/%2F/", decode=True), "/%2F/")
        with self.assertRaises(ValueError):
            case_normalize("a\nb", enforce_pchars=True)
        with self.assertRaises(ValueError):
            case_normalize("a/b", enforce_pchars=True, allow_slash=False)

    # def test_local_file_uri(self):
    #     cases = {
    #         # RFC 3986 Appendix B
    #         # POSIX paths:
    #         # ("file:///path/to/file"): empty authority, path = "/path/to/file"
    #         # A traditional file URI for a local file with an empty authority.
    #         "file:///path/to/file": PurePosixPath("/path/to/file"),
    #         # ("file:/path/to/file"): no authority, path = "/path/to/file"
    #         # The minimal representation of a local file with no authority field
    #         #   and an absolute path that begins with a slash "/".
    #         "file:/path/to/file": PurePosixPath("/path/to/file"),
    #         # Windows paths:
    #         # ("file:c:/path/to/file"): no authority, path = "c:/path/to/file"
    #         # The minimal representation of a local file in a DOS- or Windows-
    #         #   based environment with no authority field and an absolute path
    #         #   that begins with a drive letter.
    #         "file:c:/path/to/file": PureWindowsPath("C:/path/to/file"),
    #         "file:///c|/path/to/file": PureWindowsPath("C:/path/to/file"),
    #         "file:/c|/path/to/file": PureWindowsPath("C:/path/to/file"),
    #         "file:c|/path/to/file": PureWindowsPath("C:/path/to/file"),
    #     }
    #     for source, expected in cases.items():
    #         result = parse_file_uri(source)
    #         self.assertEqual(result, expected)

    # def test_nonlocal_file_uri(self):
    #     cases = {
    #         "file://host.example.com/path/to/file": urlsplit(
    #             R"file://host.example.com/path/to/file"
    #         ),
    #         # The "traditional" representation of a non-local file with an empty
    #         #   authority and a complete (transformed) UNC string in the path.
    #         "file:////host.example.com/path/to/file": PureWindowsPath(
    #             R"//host.example.com/path/to/file"
    #         ),
    #         # As above, with an extra slash between the empty authority and the
    #         #   transformed UNC string.
    #         "file://///host.example.com/path/to/file": PureWindowsPath(
    #             R"//host.example.com/path/to/file"
    #         ),
    #         # Legacy RFC 1738 example
    #         "file://vms.host.edu/disk$user/my/notes/note12345.txt": urlsplit(
    #             "file://vms.host.edu/disk$user/my/notes/note12345.txt"
    #         ),
    #     }
    #     for source, expected in cases.items():
    #         result = parse_file_uri(source)
    #         self.assertEqual(result, expected)
