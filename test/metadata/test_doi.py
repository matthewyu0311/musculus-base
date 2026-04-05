# SPDX-License-Identifier: MIT

import unittest
from urllib.parse import urlsplit


class TestDOI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global URN
        global DOI
        from musculus.metadata.doi import DOI
        from musculus.metadata.urn import URN

    def test_parse(self):
        cases = {
            # DOI Handbook or Handle System say nothing about this being invalid
            "10.1000/182": ("10.1000", "182"),
            "doi:10.1000/182": ("10.1000", "182"),
            "10.1000/456abc ": ("10.1000", "456abc "),
        }
        for expected, (prefix, suffix) in cases.items():
            doi = DOI.parse(expected)
            self.assertEqual(doi.prefix, prefix)
            self.assertEqual(doi.suffix, suffix)

    def test_resolver(self):
        cases = {
            "https://doi.org/urn:dOi:10.1000:182": ("10.1000", "182"),
            "https://dx.doi.org/10.1000/182": ("10.1000", "182"),
            # URI form can use "/" or "%2F", case insensitive
            "http://DOI.org/10.1000%2F182": ("10.1000", "182"),
        }
        for expected, (prefix, suffix) in cases.items():
            doi = DOI.from_resolver_uri(expected)
            self.assertEqual(doi.prefix, prefix)
            self.assertEqual(doi.suffix, suffix)

    def test_collation(self):
        # Example from DOI Handbook
        with self.subTest():
            # Turner & Summers (1999) "Structural Biology of HIV". Journal of Molecular Biology 285(1), pp. 1-32
            doi_jmbi = DOI.parse("10.1006/jmbi.1998.2354")
            self.assertEqual(str(doi_jmbi), "10.1006/jmbi.1998.2354")
            self.assertEqual(doi_jmbi.collate(), "10.1006/JMBI.1998.2354")
            self.assertEqual(doi_jmbi.presentation(), "doi:10.1006/jmbi.1998.2354")
            self.assertEqual(
                doi_jmbi.to_urn(),
                # 2023 standard allows "/"
                URN.parse("urn:doi:10.1006/jmbi.1998.2354"),
            )
            self.assertEqual(
                doi_jmbi.to_resolver_uri(),
                urlsplit("https://doi.org/10.1006/jmbi.1998.2354"),
            )
        with self.subTest():
            # Case-preserving but case-insensitive
            doi_lower = DOI.parse("10.1234/author123")
            doi_upper = DOI.parse("10.1234/AUTHOR123")
            self.assertNotEqual(doi_lower.suffix, doi_upper.suffix)
            self.assertEqual(doi_lower.collate(), "10.1234/AUTHOR123")
            self.assertEqual(doi_upper.collate(), "10.1234/AUTHOR123")
            self.assertEqual(doi_lower, doi_upper)

        with self.subTest():
            # Unicode normalization
            doi_umlaut_a_NFC = DOI.parse("10.2345/L\u00e4nger")
            doi_umlaut_A_NFC = DOI.parse("10.2345/L\u00c4nger")
            doi_umlaut_a_NFD = DOI.parse("10.2345/L\u0061\u0308nger")
            doi_umlaut_A_NFD = DOI.parse("10.2345/L\u0041\u0308nger")
            # ASCII-only casefolding
            # All of them should compare different...
            self.assertNotEqual(doi_umlaut_a_NFC, doi_umlaut_A_NFC)
            self.assertNotEqual(doi_umlaut_a_NFC, doi_umlaut_a_NFD)
            self.assertNotEqual(doi_umlaut_a_NFC, doi_umlaut_A_NFD)
            self.assertNotEqual(doi_umlaut_A_NFC, doi_umlaut_a_NFD)
            self.assertNotEqual(doi_umlaut_A_NFC, doi_umlaut_A_NFD)
            # but this pair should compare the same
            self.assertEqual(doi_umlaut_a_NFD, doi_umlaut_A_NFD)
            # URI quote converts to UTF-8 first, thus "%C3%A4" and not "%E4" (ord 228)

            self.assertEqual(
                doi_umlaut_a_NFC.to_resolver_uri().geturl(),
                "https://doi.org/10.2345/L%C3%A4nger",
            )

            self.assertEqual(
                doi_umlaut_A_NFC.to_resolver_uri().geturl(),
                "https://doi.org/10.2345/L%C3%84nger",
            )

            self.assertEqual(
                doi_umlaut_a_NFD.to_resolver_uri().geturl(),
                "https://doi.org/10.2345/La%CC%88nger",
            )

            self.assertEqual(
                doi_umlaut_A_NFD.to_resolver_uri().geturl(),
                "https://doi.org/10.2345/LA%CC%88nger",
            )

        for doi in (
            doi_jmbi,
            doi_lower,
            doi_upper,
            doi_umlaut_A_NFC,
            doi_umlaut_a_NFC,
            doi_umlaut_A_NFD,
            doi_umlaut_a_NFD,
        ):
            self.assertEqual(DOI.parse(str(doi)), doi)
            self.assertEqual(DOI.parse(doi.collate()), doi)
            self.assertEqual(DOI.parse(doi.presentation()), doi)
            self.assertEqual(DOI.from_urn(doi.to_urn()), doi)

            self.assertEqual(DOI.from_resolver_uri(doi.to_resolver_uri()), doi)

    def test_roundtrip(self):
        # Ugly but not explicitly forbidden characters
        # From DOI Handbook 2.6.1
        # When displayed on screen or in print, a DOI name is preceded by a lowercase "doi:"
        # unless the context clearly indicates that a DOI name is implied.
        # The "doi:" label is not part of the DOI name value.
        # No other processing is specified even if it looks really ugly for presentation purposes
        doi = DOI.parse("10.1000/456abc")
        self.assertEqual(doi, DOI.parse("10.1000/456abc"))
        self.assertEqual(str(doi), "10.1000/456abc")
        self.assertEqual(doi.collate(), "10.1000/456ABC")
        self.assertEqual(doi.presentation(), "doi:10.1000/456abc")
        self.assertEqual(doi.to_urn(), URN.parse("urn:doi:10.1000/456abc"))
        self.assertEqual(
            doi.to_resolver_uri(),
            urlsplit("https://doi.org/10.1000/456abc"),
        )
        self.assertEqual(DOI.parse(str(doi)), doi)
        self.assertEqual(DOI.parse(doi.collate()), doi)
        self.assertEqual(DOI.parse(doi.presentation()), doi)
        self.assertEqual(DOI.from_urn(doi.to_urn()), doi)

        self.assertEqual(DOI.from_resolver_uri(doi.to_resolver_uri()), doi)
