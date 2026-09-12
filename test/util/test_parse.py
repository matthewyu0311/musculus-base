import unittest


class TestParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        global ascii_casefold, make_wellformed, screaming_snake_case, pascal_case, collate
        global LooseMatchStrEnum, loose_match_boolean, mod10_check_digit
        from musculus.util.parse import (
            LooseMatchStrEnum,
            ascii_casefold,
            collate,
            loose_match_boolean,
            make_wellformed,
            mod10_check_digit,
            pascal_case,
            screaming_snake_case,
        )

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

    def test_make_wellformed(self):
        cases = [
            ("", {}, ""),
            (" abc ", {"strip": True}, "abc"),
            (" abc ", {"lstrip": True, "length": 4}, "abc "),
            (" abc ", {"rstrip": True, "length": 4}, " abc"),
            ("AbC", {"casefold": True, "length": 3}, "abc"),
            ("AbC", {"upper": True}, "ABC"),
            ("e\u0301", {"normalize": "NFC", "length": 1}, "\xe9"),
            ("AbC", {"casefold": True, "removeprefix": "a"}, "bc"),
            ("abc", {"upper": True, "removesuffix": "C"}, "AB"),
        ]
        for case, args, expected in cases:
            self.assertEqual(make_wellformed(case, **args), expected)
        negative_cases = [
            ("abc", {"length": 5}),
            ("ab c", {"no_whitespaces": True}),
            ("ab\nc", {"no_multilines": True}),
            ("abc", {"is_alpha": False}),
            ("abc1", {"is_alpha": True}),
            ("123", {"is_digit": False}),
            ("12_3", {"is_digit": True}),
            ("abc1", {"is_alnum": False}),
            ("abc1_", {"is_alnum": True}),
            ("Abc1", {"startswith": "abc"}),
            ("abc1", {"endswith": "C1"}),
            ("", {"first_chars": {"a", "b", "c"}}),
            ("dabc", {"first_chars": {"a", "b", "c"}}),
            ("abcd", {"continue_chars": {"a", "b", "c", "1", "2", "3"}}),
        ]
        for case, args in negative_cases:
            with self.assertRaises(ValueError):
                make_wellformed(case, **args)

    def test_case_change(self):
        self.assertEqual(
            screaming_snake_case("Arabic_Presentation_Forms-A"),
            "ARABIC_PRESENTATION_FORMS_A",
        )
        self.assertEqual(pascal_case("kRSUnicode"), "KRSUnicode")

    def test_loose_match(self):
        self.assertEqual(
            collate(screaming_snake_case("Arabic_Presentation_Forms-A")),
            collate("ARABIC_PRESENTATION_FORMS_A"),
        )
        self.assertEqual(collate(pascal_case("kRSUnicode")), collate("KRSUnicode"))

        class TestClass(LooseMatchStrEnum):
            ALPHA = "alp"
            BRAVO = "brAVO"
            CHARLIE = "CHArlie"
            CHARLIE_ALIAS = "CHArlie"

        cases = [
            (TestClass("ALPHA"), TestClass.ALPHA),
            (TestClass("alpha"), TestClass.ALPHA),
            (TestClass("ALP"), TestClass.ALPHA),
            (TestClass(" br-avo"), TestClass.BRAVO),
            (TestClass("Charlie"), TestClass.CHARLIE),
            (TestClass("charlie alias"), TestClass.CHARLIE),
        ]
        for case, expected in cases:
            # Enums are guaranteed to return exact identity
            self.assertIs(case, expected)

        true_cases = ["", "Y", "Yes", "T", "True"]
        false_cases = ["N", "No", "F", "False"]
        for tc in true_cases:
            self.assertTrue(loose_match_boolean(tc))
            self.assertTrue(loose_match_boolean(tc.casefold() + " "))
        for fc in false_cases:
            self.assertFalse(loose_match_boolean(fc))
            self.assertFalse(loose_match_boolean(fc.casefold() + " "))

    def test_mod10_check_digit(self):
        # For now we don't have an identifier that uses mod10, so we need to test this
        cases = {1789372997: "4", 400763000011: "6"}
        for case, expected in cases.items():
            self.assertEqual(mod10_check_digit(case), expected)
