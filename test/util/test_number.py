import unittest
from fractions import Fraction
from math import isnan, nan, pi


class TestNumberFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global BaseUnitMixin, Dimension, Scalar, clamp, frac_float, parse_roman, roman

        from musculus.util.number import (
            clamp,
            frac_float,
            parse_roman,
            roman,
        )

    def test_clamp(self):
        self.assertEqual(clamp(0, 5.5, 10.5), 5.5)
        self.assertEqual(clamp(5.5, 5.5, 10.5), 5.5)
        self.assertEqual(clamp(10.5, 5.5, 10.5), 10.5)
        self.assertTrue(isnan(clamp(nan, 5.5, 10.5)))

    def test_frac_or_float(self):
        self.assertEqual(frac_float(1.5), Fraction(3, 2))
        self.assertIsInstance(frac_float(1.5), float)

        self.assertEqual(frac_float(1), 1)
        self.assertIsInstance(frac_float(1), int)

        self.assertEqual(frac_float(Fraction(4, 2)), 2)
        self.assertIsInstance(frac_float(Fraction(4, 2)), int)
        self.assertTrue(isnan(frac_float(nan)))

    def test_roman(self):
        for n in range(4000):
            self.assertEqual(parse_roman(roman(n)), n)
