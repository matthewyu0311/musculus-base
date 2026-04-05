import unittest


class TestISMN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global URN
        global ISMN
        from musculus.metadata.ismn import ISMN
        from musculus.metadata.urn import URN

    def test_ismn(self):
        case = "979-0-3452-4680-5"
        result = ISMN.parse(case)
        self.assertEqual(result.registrant, "3452")
        self.assertEqual(result.item, "4680")
        self.assertEqual(result.check_digit, "5")

        for foo in (
            ISMN.parse(str(result)),
            ISMN.parse(result.collate()),
            ISMN.parse(result.presentation()),
            ISMN.from_urn(result.to_urn()),
        ):
            self.assertEqual(foo, result)

    def test_presentation(self):
        case = "ISMN 979-0-2600-0043-8"
        result = ISMN.parse(case)
        self.assertEqual(result.registrant, "2600")
        self.assertEqual(result.item, "0043")
        self.assertEqual(result.check_digit, "8")

        for foo in (
            ISMN.parse(str(result)),
            ISMN.parse(result.collate()),
            ISMN.parse(result.presentation()),
            ISMN.from_urn(result.to_urn()),
        ):
            self.assertEqual(foo, result)

    def test_legacy(self):
        case = "M345246805"
        result = ISMN.parse(case)
        self.assertEqual(result.registrant, "3452")
        self.assertEqual(result.item, "4680")
        self.assertEqual(result.check_digit, "5")

        for foo in (
            ISMN.parse(str(result)),
            ISMN.parse(result.collate()),
            ISMN.parse(result.presentation()),
            ISMN.from_urn(result.to_urn()),
        ):
            self.assertEqual(foo, result)
