import unittest


class TestParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        global ascii_casefold
        from musculus.util.parse import ascii_casefold

    def test_ascii_casefold(self):
        # From 2.4 Case Sensitivity:
        # DOI names are case insensitive, using ASCII case folding for comparison of text.
        # (Case insensitivity for DOI names applies only to ASCII characters.
        # DOI names which differ in the case of non-ASCII Unicode characters may be different identifiers.)
        # 10.123/ABC is identical to 10.123/AbC.
        #
        # If a DOI name were registered as 10.123/ABC, then 10.123/abc will resolve it and
        # an attempt to register 10.123/AbC would be rejected with the error message that this DOI name already existed.
        cases = {
            "10.123/AbC": "10.123/ABC",
            "10.123/abc": "10.123/ABC",
            "10.123/\uff21b\uff43": "10.123/\uff21B\uff43",  # Fullwidth "A", ASCII "b", fullwidth "c"
        }

        for case, expected in cases.items():
            self.assertEqual(ascii_casefold(case, upper=True), expected)

    # TODO: add unicode test cases