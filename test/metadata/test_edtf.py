# SPDX-License-Identifier: MIT

import datetime as dt
import unittest
from calendar import Month

from musculus.metadata.edtf import Qualifier
from musculus.util.number import make_quantity


class TestEDTF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global EDTFDate, EDTFYear, EDTFYearMonth, EDTFYearMonthDay, EDTFDateTime, EDTFOffsetDateTime, EDTFInterval, Season, parse_edtf, Qualifier
        from musculus.metadata.edtf import (
            EDTFDate,
            EDTFDateTime,
            EDTFInterval,
            EDTFOffsetDateTime,
            EDTFYear,
            EDTFYearMonth,
            EDTFYearMonthDay,
            Qualifier,
            Season,
            parse_edtf,
        )

    def test_qualifiers(self):
        cases = [
            (
                Qualifier.APPROXIMATE | Qualifier.UNCERTAIN,
                Qualifier.UNCERTAIN_AND_APPROXIMATE,
            ),
            (
                Qualifier.APPROXIMATE & Qualifier.UNCERTAIN,
                Qualifier.UNQUALIFIED,
            ),
            (
                Qualifier.UNCERTAIN_AND_APPROXIMATE ^ Qualifier.UNCERTAIN,
                Qualifier.APPROXIMATE,
            ),
            (~Qualifier.UNQUALIFIED, Qualifier.UNCERTAIN_AND_APPROXIMATE),
            (~Qualifier.APPROXIMATE, Qualifier.UNCERTAIN),
            (~Qualifier.UNCERTAIN, Qualifier.APPROXIMATE),
            (~Qualifier.UNCERTAIN_AND_APPROXIMATE, Qualifier.UNQUALIFIED),
        ]
        for case, expected in cases:
            self.assertEqual(case, expected)

    def test_parse_l0(self):
        cases = {
            "1985-04-12": EDTFYearMonthDay(1985, Month.APRIL, 12),
            "1985-04": EDTFYearMonth(1985, Month.APRIL),
            "1985": EDTFYear(1985),
            "1985-04-12T23:20:30": EDTFDateTime(1985, Month.APRIL, 12, 23, 20, 30.0),
            "1985-04-12T23:20:30Z": EDTFOffsetDateTime(
                1985, Month.APRIL, 12, 23, 20, 30.0, 0.0
            ),
            "1985-04-12T23:20:30-04": EDTFOffsetDateTime(
                1985, Month.APRIL, 12, 23, 20, 30.0, -4 * 3600.0
            ),
            "1985-04-12T23:20:30+04:30": EDTFOffsetDateTime(
                1985, Month.APRIL, 12, 23, 20, 30.0, 4.5 * 3600.0
            ),
            "1964/2008": EDTFInterval(EDTFYear(1964), EDTFYear(2008)),
            "2004-06/2006-08": EDTFInterval(
                EDTFYearMonth(2004, Month.JUNE), EDTFYearMonth(2006, Month.AUGUST)
            ),
            "2004-02-01/2005-02-08": EDTFInterval(
                EDTFYearMonthDay(2004, Month.FEBRUARY, 1),
                EDTFYearMonthDay(2005, Month.FEBRUARY, 8),
            ),
            "2004-02-01/2005-02": EDTFInterval(
                EDTFYearMonthDay(2004, Month.FEBRUARY, 1),
                EDTFYearMonth(2005, Month.FEBRUARY),
            ),
            "2004-02-01/2005": EDTFInterval(
                EDTFYearMonthDay(2004, Month.FEBRUARY, 1), EDTFYear(2005)
            ),
            "2005/2006-02": EDTFInterval(
                EDTFYear(2005), EDTFYearMonth(2006, Month.FEBRUARY)
            ),
        }
        for s, expected in cases.items():
            date = parse_edtf(s)
            self.assertIsInstance(date, type(expected))
            self.assertEqual(date, expected)

    def test_parse_l1(self):
        cases = {
            "Y170000002": EDTFYear(170000002),
            "Y-170000002": EDTFYear(-170000002),
            "2001-21": EDTFYearMonth(2001, Season.SPRING),
            "1984?": EDTFYear(1984, year_qualifier=Qualifier.UNCERTAIN),
            "2004-06~": EDTFYearMonth(
                2004,
                Month.JUNE,
                year_qualifier=Qualifier.APPROXIMATE,
                month_qualifier=Qualifier.APPROXIMATE,
            ),
            "2004-06-11%": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                year_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
                month_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
                day_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
            ),
            "1985-04-12/..": EDTFInterval(
                EDTFYearMonthDay(1985, Month.APRIL, 12), Ellipsis
            ),
            "1985-04/..": EDTFInterval(EDTFYearMonth(1985, Month.APRIL), Ellipsis),
            "1985/..": EDTFInterval(EDTFYear(1985), Ellipsis),
            "../1985-04-12": EDTFInterval(
                Ellipsis, EDTFYearMonthDay(1985, Month.APRIL, 12)
            ),
            "../1985-04": EDTFInterval(Ellipsis, EDTFYearMonth(1985, Month.APRIL)),
            "../1985": EDTFInterval(Ellipsis, EDTFYear(1985)),
            "1985-04-12/": EDTFInterval(EDTFYearMonthDay(1985, Month.APRIL, 12), None),
            "1985-04/": EDTFInterval(EDTFYearMonth(1985, Month.APRIL), None),
            "1985/": EDTFInterval(EDTFYear(1985), None),
            "/1985-04-12": EDTFInterval(None, EDTFYearMonthDay(1985, Month.APRIL, 12)),
            "/1985-04": EDTFInterval(None, EDTFYearMonth(1985, Month.APRIL)),
            "/1985": EDTFInterval(None, EDTFYear(1985)),
            "-1985": EDTFYear(-1985),
        }
        for s, expected in cases.items():
            date = parse_edtf(s)
            self.assertIsInstance(date, type(expected))
            self.assertEqual(date, expected)

    def test_parse_l2(self):
        cases = {
            "2001-34": EDTFYearMonth(2001, Season.QUARTER_2),
            "2004-06-11%": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                year_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
                month_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
                day_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
            ),
            "2004-06~-11": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                year_qualifier=Qualifier.APPROXIMATE,
                month_qualifier=Qualifier.APPROXIMATE,
            ),
            "2004?-06-11": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                year_qualifier=Qualifier.UNCERTAIN,
            ),
            "?2004-06-~11": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                year_qualifier=Qualifier.UNCERTAIN,
                day_qualifier=Qualifier.APPROXIMATE,
            ),
            "2004-%06-11": EDTFYearMonthDay(
                2004,
                Month.JUNE,
                11,
                month_qualifier=Qualifier.UNCERTAIN_AND_APPROXIMATE,
            ),
            "2004-06-~01/2004-06-~20": EDTFInterval(
                EDTFYearMonthDay(
                    2004,
                    Month.JUNE,
                    1,
                    day_qualifier=Qualifier.APPROXIMATE,
                ),
                EDTFYearMonthDay(
                    2004,
                    Month.JUNE,
                    20,
                    day_qualifier=Qualifier.APPROXIMATE,
                ),
            ),
        }
        for s, expected in cases.items():
            date = parse_edtf(s)
            self.assertIsInstance(date, type(expected))
            self.assertEqual(date, expected)

    def test_ymd_calc(self):
        dt_today = dt.date.today()
        today = EDTFYearMonthDay.from_datetime(dt_today)
        yesterday = today - 1
        self.assertIsInstance(yesterday, EDTFYearMonthDay)
        self.assertEqual(today - yesterday, 1)
        self.assertEqual(yesterday - today, -1)
        self.assertEqual(yesterday + 1, today)

    def test_comparison(self):
        year_2025 = EDTFYear(2025)
        year_2026 = EDTFYear(2026)
        ym_2025_04 = EDTFYearMonth(2025, 4)
        ymd_2025_04_07 = EDTFYearMonthDay(2025, 4, 7)

        self.assertLess(year_2025, year_2026)
        self.assertLessEqual(year_2025, year_2026)
        self.assertNotEqual(year_2025, year_2026)
        self.assertGreaterEqual(year_2026, year_2025)
        self.assertGreater(year_2026, year_2025)
        
        self.assertLess(ym_2025_04, year_2026)
        self.assertIn(ym_2025_04, year_2025)
        self.assertLessEqual(ym_2025_04, year_2025)
        
        self.assertIn(ymd_2025_04_07, ym_2025_04)