import unittest


class TestISBN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global URN
        global ISBN
        from musculus.metadata.isbn import ISBN
        from musculus.metadata.urn import URN

    def test_isbn(self):
        # ISBN Handbook Section 5
        case1 = "ISBN 978-92-95055-12-4"
        case2 = "ISBN 978 92 95055 12 4"
        result1 = ISBN.parse(case1)
        result2 = ISBN.parse(case2)
        self.assertEqual(result1.gs1, "978")
        self.assertEqual(result1.elements, ("929505512"))
        self.assertEqual(result1.check_digit, "4")
        self.assertEqual(result2.gs1, "978")
        self.assertEqual(result2.elements, ("929505512"))
        self.assertEqual(result2.check_digit, "4")
        self.assertEqual(result2, result1)

        for isbn in (result1, result2):
            self.assertEqual(ISBN.parse(str(isbn)), isbn)
            self.assertEqual(ISBN.parse(isbn.collate()), isbn)
            self.assertEqual(ISBN.parse(isbn.presentation()), isbn)
            self.assertEqual(ISBN.from_urn(isbn.to_urn()), isbn)

    def test_legacy(self):
        case = "951-0-18435-7"

        result = ISBN.parse(case)
        self.assertEqual(result.gs1, "978")
        self.assertEqual(result.elements, ("951018435"))
        self.assertEqual(result.ean13_check_digit, "6")
        self.assertEqual(result.collate(), "9789510184356")
        self.assertEqual(str(result), "978-951018435-6")
        self.assertEqual(result.presentation(), "ISBN 978-951018435-6")
        self.assertEqual(result, ISBN.parse("URN:ISBN:978-951-0-18435-6"))
