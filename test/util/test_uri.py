# SPDX-License-Identifier: MIT

import unittest
from ipaddress import IPv4Address, IPv6Address
from urllib.parse import urlsplit


class TestURI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global case_normalize, recompose_uri, dissect_uri
        from musculus.util.uri import case_normalize, dissect_uri, recompose_uri

    def test_case_normalize(self):
        # RFC 3986 2.3;
        #   For consistency, percent-encoded octets in the ranges of ALPHA
        #    (%41-%5A and %61-%7A), DIGIT (%30-%39), hyphen (%2D), period (%2E),
        #    underscore (%5F), or tilde (%7E) should not be created by URI
        #    producers and, when found in a URI, should be decoded to their
        #    corresponding unreserved characters by URI normalizers.
        self.assertEqual(case_normalize("ABC%5c%7e", casefold=True), "abc%5C~")
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

    def test_dissect(self):
        cases = {
            "http://example.com": {
                "scheme": "http",
                "username": None,
                "password": None,
                "host": "example.com",
                "is_localhost": False,
                "port": None,
                "path": [],
                "query": "",
                "fragment": "",
            },
            "http://localhost/": {
                "scheme": "http",
                "username": None,
                "password": None,
                "host": "localhost",
                "is_localhost": True,
                "port": None,
                "path": ["", ""],
                "query": "",
                "fragment": "",
            },
            "file:///etc/hosts": {
                "scheme": "file",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["", "etc", "hosts"],
                "query": "",
                "fragment": "",
            },
            "ftp://ftp.is.co.za/rfc/rfc1808.txt": {
                "scheme": "ftp",
                "username": None,
                "password": None,
                "host": "ftp.is.co.za",
                "is_localhost": False,
                "port": None,
                "path": ["", "rfc", "rfc1808.txt"],
                "query": "",
                "fragment": "",
            },
            "http://www.ietf.org/rfc/rfc2396.txt": {
                "scheme": "http",
                "username": None,
                "password": None,
                "host": "www.ietf.org",
                "is_localhost": False,
                "port": None,
                "path": ["", "rfc", "rfc2396.txt"],
                "query": "",
                "fragment": "",
            },
            "ldap://[2001:db8::7]/c=GB?objectClass?one": {
                "scheme": "ldap",
                "username": None,
                "password": None,
                "host": IPv6Address("2001:db8::7"),
                "is_localhost": False,
                "port": None,
                "path": ["", "c=GB"],
                "query": "objectClass?one",
                "fragment": "",
            },
            "mailto:John.Doe@example.com": {
                "scheme": "mailto",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["John.Doe@example.com"],
                "query": "",
                "fragment": "",
            },
            "news:comp.infosystems.www.servers.unix": {
                "scheme": "news",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["comp.infosystems.www.servers.unix"],
                "query": "",
                "fragment": "",
            },
            "tel:+1-816-555-1212": {
                "scheme": "tel",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["+1-816-555-1212"],
                "query": "",
                "fragment": "",
            },
            "telnet://192.0.2.16:80/": {
                "scheme": "telnet",
                "username": None,
                "password": None,
                "host": IPv4Address("192.0.2.16"),
                "is_localhost": False,
                "port": 80,
                "path": ["", ""],
                "query": "",
                "fragment": "",
            },
            "urn:oasis:names:specification:docbook:dtd:xml:4.1.2": {
                "scheme": "urn",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["oasis:names:specification:docbook:dtd:xml:4.1.2"],
                "query": "",
                "fragment": "",
            },
            "foo://example.com:8042/over/there?name=ferret#nose": {
                "scheme": "foo",
                "username": None,
                "password": None,
                "host": "example.com",
                "is_localhost": False,
                "port": 8042,
                "path": ["", "over", "there"],
                "query": "name=ferret",
                "fragment": "nose",
            },
            "urn:example:animal:ferret:nose": {
                "scheme": "urn",
                "username": None,
                "password": None,
                "host": None,
                "is_localhost": None,
                "port": None,
                "path": ["example:animal:ferret:nose"],
                "query": "",
                "fragment": "",
            },
        }
        for uri, expected in cases.items():
            dissected = dissect_uri(uri)
            self.assertEqual(dissected, expected)
            recomposed = recompose_uri(dissected)
            self.assertEqual(recomposed, urlsplit(uri))
