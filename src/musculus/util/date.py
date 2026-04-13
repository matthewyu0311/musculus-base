__all__ = [
    "Day0Based",
    "Day1Based",
    "format_year",
    "days_in_month",
    "ORDINAL_TO_MONTH_DAY",
    "ORDINAL_TO_MONTH_DAY_LEAP",
    "MONTH_DAY_TO_ORDINAL",
    "MONTH_DAY_TO_ORDINAL_LEAP",
    "DAYS_IN_400_YEARS",
    "DAYS_IN_100_YEARS",
    "DAYS_IN_4_YEARS",
    "AVERAGE_DAYS_PER_YEAR",
    "year_to_ordinal",
    "ordinal_to_year",
    "ordinal_to_date",
    "date_to_ordinal",
    "date_shift",
    "format_time_component",
    "Season",
    "LEAP_SECONDS",
    "epoch_seconds",
]

from calendar import Month, isleap
from enum import IntEnum
from functools import lru_cache
from typing import Literal

type Day0Based = int
type Day1Based = int


@lru_cache
def format_year(year: int) -> str:
    if 0 <= year <= 9999:
        return f"{year:04d}"
    elif -9999 <= year:
        return f"-{-year:04d}"
    elif year > 9999:
        return f"{year:06d}"
    else:
        return f"-{-year:06d}"


@lru_cache(maxsize=365 + 366)
def days_in_month(year: int, month: Month | int) -> Literal[28, 29, 30, 31]:
    match month:
        case 2:
            return 29 if isleap(year) else 28
        case 4 | 6 | 9 | 11:
            return 30
        case x if 1 <= x <= 12:
            return 31
        case _:
            raise ValueError


ORDINAL_TO_MONTH_DAY = [
    (m, d + 1) for m in Month for d in range(days_in_month(1970, m))
]
ORDINAL_TO_MONTH_DAY_LEAP = [
    (m, d + 1) for m in Month for d in range(days_in_month(1972, m))
]
MONTH_DAY_TO_ORDINAL = {v: i for i, v in enumerate(ORDINAL_TO_MONTH_DAY)}
MONTH_DAY_TO_ORDINAL_LEAP = {v: i for i, v in enumerate(ORDINAL_TO_MONTH_DAY_LEAP)}

DAYS_IN_400_YEARS = 366 * 97 + 365 * 303  # Exactly 146097 days in 400 years
DAYS_IN_100_YEARS = 366 * 24 + 365 * 76
DAYS_IN_4_YEARS = 366 + 365 * 3
AVERAGE_DAYS_PER_YEAR = DAYS_IN_400_YEARS / 400


def year_to_ordinal(y: int) -> Day0Based:
    """Returns the number of days between January 1 of this year to 1970-01-01.
    The result of 1971 is 365.
    """
    num_years_1 = y - 1970
    num_years_4 = (y - 1969) // 4
    num_years_100 = (y - 1901) // 100
    num_years_400 = (y - 1601) // 400
    return 365 * num_years_1 + num_years_4 - num_years_100 + num_years_400


def ordinal_to_year(ordinal: Day0Based) -> tuple[int, Day0Based]:
    """Returns the year and day-of-year of the specified ordinal."""
    # Get an estimate of the year first
    # Use integer division which is faster in most cases
    year_400, ordinal_adj = divmod(ordinal, DAYS_IN_400_YEARS)
    year = ordinal_adj // 365 + 400 * year_400 + 1970
    while True:
        a = year_to_ordinal(year)
        # In most cases we don't actually need to loop more than once
        if ordinal < a:
            year -= 1
            continue
        day_of_year = ordinal - a
        if day_of_year <= 364 or (day_of_year == 365 and isleap(year)):
            return year, day_of_year
        year += 1


def ordinal_to_date(ordinal: Day0Based) -> tuple[int, Month, Day1Based]:
    year, day_of_year = ordinal_to_year(ordinal)
    m = ORDINAL_TO_MONTH_DAY_LEAP if isleap(year) else ORDINAL_TO_MONTH_DAY
    try:
        month, day = m[day_of_year]
    except KeyError:
        raise AssertionError
    return year, month, day


def date_to_ordinal(year: int, month: Month, day: Day1Based) -> Day0Based:
    ordinal = year_to_ordinal(year)
    m = MONTH_DAY_TO_ORDINAL_LEAP if isleap(year) else MONTH_DAY_TO_ORDINAL
    try:
        return ordinal + m[(month, day)]
    except KeyError:
        raise ValueError(f"Month and day out of range: {month!r}, {day!r}")


def date_shift(
    year: int, month: Month, day: Day1Based, delta_day: int
) -> tuple[int, Month, Day1Based]:
    if delta_day == 0:
        return (year, month, day)
    if 1 <= day + delta_day <= days_in_month(year, month):
        return (year, month, day + delta_day)
    return ordinal_to_date(date_to_ordinal(year, month, day) + delta_day)


def format_time_component(t: float) -> str:
    if t < 0:
        raise ValueError(f"Time component out of range: {t!r}")
    s = f"{t:0.9f}"
    a, dot, b = s.partition(".")
    b = b.rstrip("0")
    if len(a) == 1:
        a = "0" + a
    if b:
        return a + "." + b
    return a


class Season(IntEnum):
    """The semantics of seasons (the part of the year to which they correspond) has not been well-defined by specification."""

    SPRING = 21
    SUMMER = 22
    AUTUMN = 23
    WINTER = 24
    SPRING_NORTHERN_HEMISPHERE = 25
    SUMMER_NORTHERN_HEMISPHERE = 26
    AUTUMN_NORTHERN_HEMISPHERE = 27
    WINTER_NORTHERN_HEMISPHERE = 28
    SPRING_SOUTHERN_HEMISPHERE = 29
    SUMMER_SOUTHERN_HEMISPHERE = 30
    AUTUMN_SOUTHERN_HEMISPHERE = 31
    WINTER_SOUTHERN_HEMISPHERE = 32
    QUARTER_1 = 33
    QUARTER_2 = 34
    QUARTER_3 = 35
    QUARTER_4 = 36
    QUADRIMESTER_1 = 37
    QUADRIMESTER_2 = 38
    QUADRIMESTER_3 = 39
    SEMESTRAL_1 = 40
    SEMESTRAL_2 = 41


# At the time of Resolution 4 of the 27th CGPM (2022),
# there have been a total of 27 positive leap seconds and no negatives.
# UT1 - UTC has been increasing since 2020 and is unlikely to reach
# -0.9 (where positive leap second kicks in) before 2035

LEAP_SECONDS = (
    (1972, 6, 30),
    (1972, 12, 31),
    (1973, 12, 31),
    (1974, 12, 31),
    (1975, 12, 31),
    (1976, 12, 31),
    (1977, 12, 31),
    (1978, 12, 31),
    (1979, 12, 31),
    (1981, 6, 30),
    (1982, 6, 30),
    (1983, 6, 30),
    (1985, 6, 30),
    (1987, 12, 31),
    (1989, 12, 31),
    (1990, 12, 31),
    (1992, 6, 30),
    (1993, 6, 30),
    (1994, 6, 30),
    (1995, 12, 31),
    (1997, 6, 30),
    (1998, 12, 31),
    (2005, 12, 31),
    (2008, 12, 31),
    (2012, 6, 30),
    (2015, 6, 30),
    (2016, 12, 31),
)


def epoch_seconds(year, month, day, hour, minute, second, offset_seconds):
    # XXX: Unix epoch second doesn't take leap seconds into account
    days = date_to_ordinal(year, month, day)
    return days * 86400 + hour * 3600 + minute * 60 + second + offset_seconds
