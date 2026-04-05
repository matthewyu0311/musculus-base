# SPDX-License-Identifier: MIT

import unittest


class TestEAN13Code(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global EAN13Code
        from musculus.metadata.ean13 import EAN13Code

    def test_ean13(self):
        parsed = EAN13Code.parse("977-92-95055-12-5")
        not_isbn = EAN13Code(977929505512)
        self.assertIs(type(parsed), EAN13Code)
        self.assertEqual(not_isbn, parsed)
