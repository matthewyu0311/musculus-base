# SPDX-License-Identifier: MIT

"""All test cases are taken from RFC 8141 examples."""
import itertools
import unittest


class TestURN(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global URN
        from musculus.metadata.urn import URN

    def test_urn(self):
        case = "urn:example:1/406/47452/2"
        result = URN.parse(case)
        assert result.nid == "example"
        assert result.nss == "1/406/47452/2"
        assert str(result) == case

    def test_r_component(self):
        # r-component
        case = "urn:example:foo-bar-baz-qux?+CCResolve:cc=uk"
        result = URN.parse(case)
        assert result.nid == "example"
        assert result.nss == "foo-bar-baz-qux"
        assert str(result) == case.partition("#")[0].partition("?")[0]

    def test_q_component(self):
        # q-component
        case = "urn:example:weather?=op=map&lat=39.56&lon=-104.85&datetime=1969-07-21T02:56:15Z"
        result = URN.parse(case)
        assert result.nid == "example"
        assert result.nss == "weather"
        assert str(result) == case.partition("#")[0].partition("?")[0]

    def test_f_component(self):
        # f-component
        case = "urn:example:foo-bar-baz-qux#somepart"
        result = URN.parse(case)
        assert result.nid == "example"
        assert result.nss == "foo-bar-baz-qux"
        assert str(result) == case.partition("#")[0].partition("?")[0]

    def test_urn_equivalence(self):
        # Taken from 3.2 Examples
        case5 = "urn:example:a123,z456"
        case6 = "URN:example:a123,z456"
        case7 = "urn:EXAMPLE:a123,z456"
        result5 = URN.parse(case5)
        result6 = URN.parse(case6)
        result7 = URN.parse(case7)
        # NID is stored in the lowercase form
        assert result5.nid == "example"
        assert result6.nid == "example"
        assert result7.nid == "example"
        for foo, bar in itertools.combinations((result5, result6, result7), 2):
            assert foo == bar

        with self.subTest():
            # r-, q-, f-components are not taken into account when determining equivalence
            case8 = "urn:example:a123,z456?+abc"
            case9 = "urn:example:a123,z456?=xyz"
            case10 = "urn:example:a123,z456#789"
            result8 = URN.parse(case8)
            result9 = URN.parse(case9)
            result10 = URN.parse(case10)
            for foo, bar in itertools.combinations(
                (result5, result8, result9, result10), 2
            ):
                assert foo == bar

        with self.subTest():
            # The below are NOT equivalent to one another or any of the above
            case11 = "urn:example:a123,z456/foo"
            case12 = "urn:example:a123,z456/bar"
            case13 = "urn:example:a123,z456/baz"
            result11 = URN.parse(case11)
            result12 = URN.parse(case12)
            result13 = URN.parse(case13)
            assert result11.nss == "a123,z456/foo"
            assert result12.nss == "a123,z456/bar"
            assert result13.nss == "a123,z456/baz"
            for foo, bar in itertools.combinations(
                (result5, result11, result12, result13), 2
            ):
                assert foo != bar

        with self.subTest():
            # The below are equivalent only to each other and none of the above
            case14 = "urn:example:a123%2Cz456"
            case15 = "URN:EXAMPLE:a123%2cz456"
            result14 = URN.parse(case14)
            result15 = URN.parse(case15)
            assert result14.nss == "a123%2Cz456"
            assert result15.nss == "a123%2Cz456"
            assert result14 == result15
            assert result14 != result5
            assert result15 != result5

        with self.subTest():
            # The below are not equivalent to each other or any of the above
            case16 = "urn:example:A123,z456"
            case17 = "urn:example:a123,Z456"
            result16 = URN.parse(case16)
            result17 = URN.parse(case17)
            assert result16.nss == "A123,z456"
            assert result17.nss == "a123,Z456"
            assert result16 != result17

        with self.subTest():
            # This one has a U+0430 CYRILLIC SMALL LETTER A
            # and is not equivalent to any of the above
            case18 = "urn:example:%D0%B0123,z456"
            result18 = URN.parse(case18)
            assert result18.nid == "example"
            assert result18.nss == "%D0%B0123,z456"
            assert URN.parse(str(result18)) == result18
            assert str(result18) == case18
            assert result18 != result5

    def test_urn_namespaces(self):
        case19 = "urn:example:apple:pear:plum:cherry"
        result19 = URN.parse(case19)
        assert result19.nid == "example"
        assert result19.nss == "apple:pear:plum:cherry"
        assert URN.parse(str(result19)) == result19
        assert str(result19) == case19
