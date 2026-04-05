# SPDX-License-Identifier: MIT

import unittest


class TestISAN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global URN
        global ISAN
        from musculus.metadata.isan import ISAN
        from musculus.metadata.urn import URN

    def test_isan(self):
        with self.subTest():
            case1 = "0000-0000-3A8D-0000-Z-0000-0000-6"
            result1 = ISAN.parse(case1)
            self.assertEqual(str(result1), case1)
            self.assertEqual(result1.collate(), "000000003A8D000000000000")
            self.assertEqual(
                result1.presentation(), "ISAN 0000-0000-3A8D-0000-Z-0000-0000-6"
            )
            self.assertEqual(
                result1.to_urn(),
                URN.parse("urn:isan:0000-0000-3A8D-0000-Z-0000-0000-6"),
            )
            self.assertEqual(
                result1.to_resolver_uri().geturl(),
                "https://www.isan.org/lookup/ISAN%200000-0000-3A8D-0000-Z-0000-0000-6",
            )

        with self.subTest():
            case2 = "URN:ISAN:0000-0000-3A8D-0000-Z-0000-0000-6"
            result2 = ISAN.from_urn(URN.parse(case2))
            self.assertEqual(result2, result1)

        with self.subTest():
            case3 = "0000-0000-3a8D-0000-z-0000-0000-6"
            result3 = ISAN.parse(case3)
            self.assertEqual(result3, result1)

        # Wrong first check digit
        self.assertRaises(ValueError, ISAN.parse, "0000-0000-3A8D-0000-Y-0000-0000-6")
        # Wrong second check digit
        self.assertRaises(ValueError, ISAN.parse, "0000-0000-3A8D-0000-Z-0000-0000-5")

        for isan in (result1, result2):
            self.assertEqual(ISAN.parse(str(isan)), isan)
            self.assertEqual(ISAN.parse(isan.collate()), isan)
            self.assertEqual(ISAN.parse(isan.presentation()), isan)
            self.assertEqual(ISAN.from_urn(isan.to_urn()), isan)
            self.assertEqual(ISAN.from_resolver_uri(isan.to_resolver_uri()), isan)
