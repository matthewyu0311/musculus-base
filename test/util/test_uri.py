# SPDX-License-Identifier: MIT

# import unittest

# from pathlib import PurePosixPath, PureWindowsPath
# from urllib.parse import urlsplit


# class TestURI(unittest.TestCase):
# @classmethod
# def setUpClass(cls):
#     global parse_file_uri
#     from musculus.util.uri import parse_file_uri

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
