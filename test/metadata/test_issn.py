# SPDX-License-Identifier: MIT

import unittest


class TestISSN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global ISSN, URN
        from musculus.metadata.issn import ISSN
        from musculus.metadata.urn import URN

    def test_issn(self):
        case = "0317-8471"  # Vers demain
        result = ISSN.parse(case)
        self.assertEqual(result.collate(), "03178471")

        for foo in (
            ISSN.parse(str(result)),
            ISSN.parse(result.collate()),
            ISSN.parse(result.presentation()),
            ISSN.from_urn(result.to_urn()),
            ISSN.from_resolver_uri(result.to_resolver_uri()),
        ):
            self.assertEqual(foo, result)

    def test_presentation(self):
        case = "ISSN 1050-124X"
        result = ISSN.parse(case)
        self.assertEqual(result.collate(), "1050124X")

        for foo in (
            ISSN.parse(str(result)),
            ISSN.parse(result.collate()),
            ISSN.parse(result.presentation()),
            ISSN.from_urn(result.to_urn()),
            ISSN.from_resolver_uri(result.to_resolver_uri()),
        ):
            self.assertEqual(foo, result)

    def test_parse(self):
        # https://www.issn.org/understanding-the-issn/issn-uses/identification-with-the-ean-13-barcode/
        # NOTE: The conversion from EAN-13 to ISSN is one-way
        case = "977-1144-875-007"
        result = ISSN.parse(case)

        self.assertEqual(result, ISSN.parse("1144-875X"))
        self.assertEqual(result.collate(), "1144875X")
        self.assertEqual(str(result), "1144-875X")
        self.assertEqual(result.presentation(), "ISSN 1144-875X")
