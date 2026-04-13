__all__ = [
    "DateKey",
    "Qualifier",
    "PATTERN_FLAGS",
    "YEAR_PATTERN",
    "YEAR_MONTH_PATTERN",
    "YEAR_MONTH_DAY_PATTERN",
    "MONTH_DAY_PATTERN",
    "LAST_COMPONENT_PATTERN",
    "TIME_PATTERN",
    "DURATION_PATTERN",
    "Open",
    "EDTFDate",
    "parse_edtf",
    "EDTFYear",
    "EDTFYearMonth",
    "EDTFYearMonthDay",
    "EDTFDateTime",
    "EDTFOffsetDateTime",
    "EDTFInterval",
]

import datetime as dt
import re
from abc import abstractmethod
from calendar import Month
from enum import StrEnum
from math import copysign, fma
from types import EllipsisType
from typing import Any, Literal, Self, overload

from ..util.date import (
    Day1Based,
    Season,
    date_shift,
    date_to_ordinal,
    days_in_month,
    epoch_seconds,
    format_time_component,
    format_year,
)
from ..util.functions import (
    eq_slots,
    eq_slots_noshort,
    hash_slots,
    immutable,
    make_compare_fns,
    new_with_fields,
    repr_slots,
    runtime_final,
)
from ..util.number import int10
from ..util.parse import Parseable, ValidityError, WellFormednessError

type DateKey = tuple[int, int, int, int, int, float]


class Qualifier(StrEnum):
    # Yes, this acts more like a Flag in essence, but there's more value keeping it a string

    UNQUALIFIED = ""
    UNCERTAIN = "?"
    APPROXIMATE = "~"
    UNCERTAIN_AND_APPROXIMATE = "%"

    @classmethod
    def _missing_(cls, value):
        if value == "?~" or value == "~?":
            return cls.UNCERTAIN_AND_APPROXIMATE
        raise ValueError(f"Unknown qualifier: {value!r}")

    @property
    def is_uncertain(self) -> bool:
        return self.value == "?" or self.value == "%"

    @property
    def is_approximate(self) -> bool:
        return self.value == "~" or self.value == "%"

    @classmethod
    def of(cls, uncertain: bool, approximate: bool):
        match uncertain, approximate:
            case True, True:
                return cls.UNCERTAIN_AND_APPROXIMATE
            case True, False:
                return cls.UNCERTAIN
            case False, True:
                return cls.APPROXIMATE
            case _:
                return cls.UNQUALIFIED

    def __sub__(self, other: Qualifier) -> Qualifier:
        try:
            o = Qualifier(other)
        except ValueError:
            return NotImplemented
        else:
            approximate = self.is_approximate and not o.is_approximate
            uncertain = self.is_uncertain and not o.is_uncertain
            return Qualifier.of(uncertain, approximate)

    def __rsub__(self, other: Qualifier) -> Qualifier:
        try:
            o = Qualifier(other)
        except ValueError:
            return NotImplemented
        else:
            approximate = o.is_approximate and not self.is_approximate
            uncertain = o.is_uncertain and not self.is_uncertain
            return Qualifier.of(uncertain, approximate)

    def __and__(self, other: Qualifier) -> Qualifier:
        try:
            o = Qualifier(other)
        except ValueError:
            return NotImplemented
        else:
            approximate = self.is_approximate and o.is_approximate
            uncertain = self.is_uncertain and o.is_uncertain
            return Qualifier.of(uncertain, approximate)

    def __or__(self, other: Qualifier) -> Qualifier:
        try:
            o = Qualifier(other)
        except ValueError:
            return NotImplemented
        else:
            approximate = self.is_approximate or o.is_approximate
            uncertain = self.is_uncertain or o.is_uncertain
            return Qualifier.of(uncertain, approximate)

    def __xor__(self, other: Qualifier) -> Qualifier:
        try:
            o = Qualifier(other)
        except ValueError:
            return NotImplemented
        else:
            approximate = self.is_approximate ^ o.is_approximate
            uncertain = self.is_uncertain ^ o.is_uncertain
            return Qualifier.of(uncertain, approximate)

    def __invert__(self):
        return Qualifier.of(not self.is_uncertain, not self.is_approximate)

    __rand__ = __and__
    __ror__ = __or__
    __rxor__ = __xor__


PATTERN_FLAGS = re.ASCII | re.IGNORECASE

YEAR_PATTERN = re.compile(
    r"(?P<yq1>[~%?]?)Y?(?P<year>[+-]?\d{4,})(?P<yq2>[~%?]?)$", PATTERN_FLAGS
)
YEAR_MONTH_PATTERN = re.compile(
    r"(?P<yq1>[~%?]?)(?P<year>[+-]?\d{4,})(?P<yq2>[~%?]?)-(?P<mq>[~%?]?)(?P<month>\d\d)(?P<ymq>[~%?]?)$",
    PATTERN_FLAGS,
)
YEAR_MONTH_DAY_PATTERN = re.compile(
    r"(?P<yq1>[~%?]?)(?P<year>[+-]?\d{4,})(?P<yq2>[~%?]?)-(?P<mq>[~%?]?)(?P<month>\d\d)(?P<ymq>[~%?]?)-(?P<dq>[~%?]?)(?P<day>\d\d)(?P<ymdq>[~%?]?)$",
    PATTERN_FLAGS,
)

MONTH_DAY_PATTERN = re.compile(
    r"(?P<mq>[~%?]?)(?P<month>\d\d)(?P<ymq>[~%?]?)-(?P<dq>[~%?]?)(?P<day>\d\d)(?P<ymdq>[~%?]?)$",
    PATTERN_FLAGS,
)

LAST_COMPONENT_PATTERN = re.compile(
    r"(?P<dq>[~%?]?)(?P<day>\d\d)(?P<ymdq>[~%?]?)$",
    PATTERN_FLAGS,
)

TIME_PATTERN = re.compile(
    r"(?P<h>\d\d\.\d+$|\d\d)(:?(?P<m>\d\d\.\d+$|\d\d)(:?(?P<s>\d\d(\.\d+)?))?)?",
    PATTERN_FLAGS,
)

DURATION_PATTERN = re.compile(
    r"P(?P<weeks>\d*\.\d+|\d+)W$|"
    r"P(?P<years>\d*\.\d+Y$|\d+Y)?(?P<months>\d*\.\d+M$|\d+M)?(?P<days>\d*\.\d+D$|\d+D)?"
    r"(T(?P<hours>\d*\.\d+H$|\d+H)?(?P<minutes>\d*\.\d+M$|\d+M)?(?P<seconds>\d*\.\d+S$|\d+S)?)?",
    PATTERN_FLAGS,
)

# We treat None as meaning "the same as the other side"
# If both first and last are None, it never overlaps with anything, not even Open
# We treat Open as -infinity or infinity
Open = EllipsisType


def _fix_up_none(s1, s2, o1, o2) -> tuple[Any, Any, Any, Any]:
    match s1, s2:
        case None, None:
            raise ValueError
        case _, None:
            s2 = s1
        case None, _:
            s1 = s2
        case _:
            pass
    match o1, o2:
        case None, None:
            raise ValueError
        case _, None:
            o2 = o1
        case None, _:
            o1 = o2
        case _:
            pass
    return s1, s2, o1, o2


def _make_compare_fn(compare_fn, *, short: bool):
    def fn(self, other):
        if self is other:
            return short
        if not isinstance(other, _EDTFComparable):
            return NotImplemented
        s1, s2 = self._compare_key()
        o1, o2 = other._compare_key()
        if s2 is Ellipsis or o1 is Ellipsis:
            return short
        try:
            _, s_2, o_1, _ = _fix_up_none(s1, s2, o1, o2)
        except ValueError:
            return False
        return compare_fn

    return fn


class _EDTFComparable:
    @abstractmethod
    def _compare_key(self) -> tuple[DateKey | Open | None, DateKey | Open | None]: ...

    __lt__ = _make_compare_fn(lambda a, b, c, d: b < c, short=False)
    __le__ = _make_compare_fn(lambda a, b, c, d: a <= d, short=True)
    __ge__ = _make_compare_fn(lambda a, b, c, d: b >= c, short=True)
    __gt__ = _make_compare_fn(lambda a, b, c, d: a > d, short=False)
    __contains__ = _make_compare_fn(lambda a, b, c, d: c >= a and d <= b, short=True)

    __eq__ = eq_slots
    __hash__ = hash_slots


class EDTFDate(_EDTFComparable, Parseable):
    __slots__ = ()
    edtf_level: Literal[0, 1, 2]

    @abstractmethod
    def to_edtf_level(self, level: Literal[0, 1, 2]): ...

    @abstractmethod
    def unqualified(self) -> EDTFDate: ...

    @classmethod
    def parse(cls, source: str, /) -> EDTFDate:
        for t in [EDTFYear, EDTFYearMonth, EDTFYearMonthDay]:
            try:
                return t.parse(source)
            except IndexError, ValueError:
                continue
        raise WellFormednessError(f"Source cannot be parsed as EDTF date: {source!r}")


def parse_edtf(
    source: str, /
) -> EDTFInterval | EDTFOffsetDateTime | EDTFDateTime | EDTFDate:
    if "/" in source:
        return EDTFInterval.parse(source)
    source = source.upper()
    if "T" in source:
        try:
            return EDTFOffsetDateTime.parse(source)
        except ValueError:
            return EDTFDateTime.parse(source)
    return EDTFDate.parse(source)


@runtime_final
class EDTFYear(EDTFDate):
    __slots__ = ("year", "year_qualifier")

    year: int
    year_qualifier: Qualifier

    def _compare_key(self) -> tuple[DateKey, DateKey]:
        start = (self.year, 1, 1, 0, 0, 0.0)
        end = (self.year, 12, 31, 24, 0, 0.0)
        return start, end

    def __new__(
        cls, year: int, *, year_qualifier: Qualifier | str = Qualifier.UNQUALIFIED
    ) -> Self:
        return new_with_fields(cls, year=year, year_qualifier=Qualifier(year_qualifier))

    @property
    def edtf_level(self) -> Literal[0, 1]:
        if self.year_qualifier != Qualifier.UNQUALIFIED or not 0 <= self.year <= 9999:
            return 1
        return 0

    def to_edtf_level(self, level: Literal[0, 1, 2]) -> Self:
        if level == 0 and not -9999 <= self.year <= 9999:
            raise ValueError("Year outside of EDTF Level 0 range")
        return self

    def __repr__(self) -> str:
        s = f"{self.__class__.__qualname__}({self.year:d}"
        if self.year_qualifier != Qualifier.UNQUALIFIED:
            s += f", year_qualifier=Qualifier.{self.year_qualifier.name}"
        return s + ")"

    def __str__(self) -> str:
        if -9999 <= self.year <= 9999:
            return f"{self.year:04d}{self.year_qualifier!s}"
        return f"Y{self.year:d}{self.year_qualifier!s}"

    def unqualified(self) -> EDTFYear:
        if self.year_qualifier == Qualifier.UNQUALIFIED:
            return self
        return EDTFYear(self.year)

    @classmethod
    def parse(cls, source: str, /) -> Self:
        m = YEAR_PATTERN.fullmatch(source)
        if m is None:
            raise WellFormednessError(
                f"Source cannot be parsed as EDTF Year: {source!r}"
            )
        gd = m.groupdict()
        yq = Qualifier(gd["yq1"]) | Qualifier(gd["yq2"])
        year = int10(gd["year"])
        return cls(year, year_qualifier=yq)


@immutable
class EDTFYearMonth(EDTFDate):
    __slots__ = ("year", "month", "year_qualifier", "month_qualifier")

    year: int
    month: Month | Season
    year_qualifier: Qualifier
    month_qualifier: Qualifier

    def _compare_key(self) -> tuple[DateKey, DateKey]:
        start = (self.year, self.month, 0 if self.month > 12 else 1, 0, 0, 0.0)
        end = (self.year, self.month, self.days_in_month or 0, 24, 0, 0.0)
        return start, end

    def __new__(
        cls,
        year: int,
        month: Month | Season | int,
        *,
        year_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
        month_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
    ) -> Self:
        try:
            month = Month(month)
        except ValueError:
            try:
                month = Season(month)
            except ValueError:
                raise ValidityError(f"Invalid month or season: {month!r}")
        return new_with_fields(
            cls,
            year=year,
            month=month,
            year_qualifier=Qualifier(year_qualifier),
            month_qualifier=Qualifier(month_qualifier),
        )

    @property
    def days_in_month(self) -> int | None:
        if self.month <= 12:
            return days_in_month(self.year, self.month)

    def unqualified(self) -> EDTFYearMonth:
        if self.year_qualifier == self.month_qualifier == Qualifier.UNQUALIFIED:
            return self
        return EDTFYearMonth(self.year, self.month)

    @property
    def edtf_level(self) -> Literal[0, 1, 2]:
        if self.month >= 25 or self.month_qualifier != self.year_qualifier:
            return 2
        elif self.month > 12 or self.month_qualifier != Qualifier.UNQUALIFIED:
            return 1
        elif not -9999 <= self.year <= 9999:
            return 1
        return 0

    @overload
    def to_edtf_level(self, level: Literal[1, 2]) -> EDTFYearMonth: ...
    @overload
    def to_edtf_level(self, level: Literal[0]) -> EDTFYearMonth | EDTFYear: ...
    def to_edtf_level(self, level: Literal[0, 1, 2]) -> EDTFYearMonth | EDTFYear:
        if level == 2 or level >= self.edtf_level:
            return self
        elif level == 1:
            q = self.year_qualifier | self.month_qualifier
            match self.month:
                case Month() as month:
                    pass
                case (
                    Season.SPRING
                    | Season.SPRING_NORTHERN_HEMISPHERE
                    | Season.SPRING_SOUTHERN_HEMISPHERE
                ):
                    month = Season.SPRING
                case (
                    Season.SUMMER
                    | Season.SUMMER_NORTHERN_HEMISPHERE
                    | Season.SUMMER_SOUTHERN_HEMISPHERE
                ):
                    month = Season.SUMMER
                case (
                    Season.AUTUMN
                    | Season.AUTUMN_NORTHERN_HEMISPHERE
                    | Season.AUTUMN_SOUTHERN_HEMISPHERE
                ):
                    month = Season.AUTUMN
                case (
                    Season.WINTER
                    | Season.WINTER_NORTHERN_HEMISPHERE
                    | Season.WINTER_SOUTHERN_HEMISPHERE
                ):
                    month = Season.WINTER
                case _:
                    return EDTFYear(self.year, year_qualifier=self.year_qualifier)
            return EDTFYearMonth(self.year, month, year_qualifier=q, month_qualifier=q)
        else:
            if not -9999 <= self.year <= 9999:
                raise ValueError("Year outside of EDTF Level 0 range")
            if self.month > 12:
                return EDTFYear(self.year)
            return EDTFYearMonth(self.year, self.month)

    def __repr__(self) -> str:
        s = f"{self.__class__.__qualname__}({self.year:d}, {self.month:d}"
        if self.year_qualifier != Qualifier.UNQUALIFIED:
            s += f", year_qualifier=Qualifier.{self.year_qualifier.name}"
        if self.month_qualifier != Qualifier.UNQUALIFIED:
            s += f", month_qualifier=Qualifier.{self.month_qualifier.name}"
        return s + ")"

    def __str__(self) -> str:
        ymq = self.year_qualifier & self.month_qualifier
        yq = self.year_qualifier - ymq
        mq = self.month_qualifier - ymq
        return f"{format_year(self.year)}{yq}-{mq}{self.month:02d}{ymq}"

    @classmethod
    def parse(cls, source: str, /) -> Self:
        m = YEAR_MONTH_PATTERN.fullmatch(source)
        if m is None:
            raise WellFormednessError(
                f"Source cannot be parsed as EDTF Year-Month: {source!r}"
            )
        gd = m.groupdict()
        ymq = Qualifier(gd["ymq"])
        yq = Qualifier(gd["yq1"]) | Qualifier(gd["yq2"]) | ymq
        mq = Qualifier(gd["mq"]) | ymq
        year = int10(gd["year"])
        month = int10(gd["month"])
        return cls(year, month, year_qualifier=yq, month_qualifier=mq)


def _edtf_ymd_str(
    year, month, day, year_qualifier, month_qualifier, day_qualifier
) -> str:
    ymdq = year_qualifier & month_qualifier & day_qualifier
    dq = day_qualifier - ymdq
    ymq = year_qualifier & month_qualifier - ymdq
    yq = year_qualifier - ymq - ymdq
    mq = month_qualifier - ymq - ymdq
    return f"{format_year(year)}{yq}-{mq}{month:02d}{ymq}-{dq}{day:02d}{ymdq}"


def _edtf_ymd_parse(source: str):
    m = YEAR_MONTH_DAY_PATTERN.fullmatch(source)
    if m is None:
        raise WellFormednessError(f"Source cannot be parsed as EDTF Date: {source!r}")
    gd = m.groupdict()
    ymdq = Qualifier(gd["ymdq"])
    ymq = Qualifier(gd["ymq"])
    yq = Qualifier(gd["yq1"]) | Qualifier(gd["yq2"]) | ymq | ymdq
    mq = Qualifier(gd["mq"]) | ymq | ymdq
    dq = Qualifier(gd["dq"]) | ymdq
    year = int10(gd["year"])
    month = int10(gd["month"])
    day = int10(gd["day"])
    return dict(
        year=year,
        month=month,
        day=day,
        year_qualifier=yq,
        month_qualifier=mq,
        day_qualifier=dq,
    )


@immutable
class EDTFYearMonthDay(EDTFDate):
    __slots__ = (
        "year",
        "month",
        "day",
        "year_qualifier",
        "month_qualifier",
        "day_qualifier",
    )
    year: int
    month: Month
    day: Day1Based
    year_qualifier: Qualifier
    month_qualifier: Qualifier
    day_qualifier: Qualifier

    def _compare_key(self) -> tuple[DateKey, DateKey]:
        start = (self.year, self.month, self.day, 0, 0, 0.0)
        end = (self.year, self.month, self.day, 24, 0, 0.0)
        return start, end

    def __new__(
        cls,
        year: int,
        month: Month | int,
        day: Day1Based,
        *,
        year_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
        month_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
        day_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
    ) -> Self:
        try:
            dim = days_in_month(year, month)
        except ValueError:
            raise ValidityError("Season cannot be used with day precision")
        if not 1 <= day <= dim:
            raise ValidityError(f"Day out of range: {day!r}")
        month = Month(month)
        return new_with_fields(
            cls,
            year=year,
            month=month,
            day=day,
            year_qualifier=Qualifier(year_qualifier),
            month_qualifier=Qualifier(month_qualifier),
            day_qualifier=Qualifier(day_qualifier),
        )

    @classmethod
    def from_datetime(cls, dt_date: dt.date, /) -> Self:
        return cls(dt_date.year, dt_date.month, dt_date.day)

    def to_datetime(self) -> dt.date:
        return dt.date(self.year, self.month, self.day)

    def unqualified(self) -> EDTFYearMonthDay:
        if (
            self.year_qualifier
            == self.month_qualifier
            == self.day_qualifier
            == Qualifier.UNQUALIFIED
        ):
            return self
        return EDTFYearMonthDay(self.year, self.month, self.day)

    @property
    def edtf_level(self) -> Literal[0, 1, 2]:
        if not self.year_qualifier == self.month_qualifier == self.day_qualifier:
            return 2
        if not -9999 <= self.year <= 9999:
            return 1
        if self.year_qualifier | self.month_qualifier | self.day_qualifier:
            return 1
        return 0

    def to_edtf_level(self, level: Literal[0, 1, 2]) -> Self:
        if level == 2 or level >= self.edtf_level:
            return self
        elif level == 1:
            q = self.year_qualifier | self.month_qualifier | self.day_qualifier
            return self.__class__(
                self.year,
                self.month,
                self.day,
                year_qualifier=q,
                month_qualifier=q,
                day_qualifier=q,
            )
        else:
            if not -9999 <= self.year <= 9999:
                raise ValueError("Year outside of EDTF Level 0 range")
            return self.__class__(self.year, self.month, self.day)

    def __repr__(self) -> str:
        s = f"{self.__class__.__qualname__}({self.year:d}, {self.month:d}, {self.day:d}"
        if self.year_qualifier != Qualifier.UNQUALIFIED:
            s += f", year_qualifier=Qualifier.{self.year_qualifier.name}"
        if self.month_qualifier != Qualifier.UNQUALIFIED:
            s += f", month_qualifier=Qualifier.{self.month_qualifier.name}"
        if self.day_qualifier != Qualifier.UNQUALIFIED:
            s += f", day_qualifier=Qualifier.{self.day_qualifier.name}"
        return s + ")"

    def __str__(self) -> str:
        return _edtf_ymd_str(
            self.year,
            self.month,
            self.day,
            self.year_qualifier,
            self.month_qualifier,
            self.day_qualifier,
        )

    @classmethod
    def parse(cls, source: str, /) -> Self:
        return cls(**_edtf_ymd_parse(source))  # type: ignore

    def __add__(self, other: int | dt.timedelta) -> EDTFYearMonthDay:
        td = dt.timedelta
        match other:
            case int(d) | td(days=d):
                if not other:
                    return self
                return EDTFYearMonthDay(
                    *date_shift(self.year, self.month, self.day, d),
                    year_qualifier=self.year_qualifier,
                    month_qualifier=self.month_qualifier,
                    day_qualifier=self.day_qualifier,
                )
            case _:
                return NotImplemented

    __radd__ = __add__

    @overload
    def __sub__(self, other: int | dt.timedelta) -> EDTFYearMonthDay: ...

    @overload
    def __sub__(self, other: EDTFYearMonthDay) -> int: ...

    def __sub__(
        self, other: int | dt.timedelta | EDTFYearMonthDay
    ) -> EDTFYearMonthDay | int:
        td = dt.timedelta
        match other:
            case int(d) | td(days=d):
                if not other:
                    return self
                return EDTFYearMonthDay(
                    *date_shift(self.year, self.month, self.day, -d),
                    year_qualifier=self.year_qualifier,
                    month_qualifier=self.month_qualifier,
                    day_qualifier=self.day_qualifier,
                )
            case EDTFYearMonthDay():
                return date_to_ordinal(
                    self.year, self.month, self.day
                ) - date_to_ordinal(other.year, other.month, other.day)
            case _:
                return NotImplemented


def _edtf_dt_parse(source: str):
    date, _, time = source.upper().partition("T")
    tm = TIME_PATTERN.fullmatch(time)
    if tm is None:
        raise WellFormednessError(
            f"Source cannot be parsed as EDTF date-time: {source!r}"
        )
    gd = tm.groupdict()
    hour = float(gd["h"])
    try:
        minute = float(gd["m"])
    except TypeError, ValueError:
        minute = 0.0
    try:
        second = float(gd["s"])
    except TypeError, ValueError:
        second = 0.0
    if not hour.is_integer():
        hour_part = int(hour)
        minute += (hour - hour_part) * 60
        hour = hour_part
    if not minute.is_integer():
        minute_part = int(minute)
        second += (hour - hour_part) * 60
        minute = minute_part
    return {
        **_edtf_ymd_parse(date),
        "hour": int(hour),
        "minute": int(minute),
        "second": second,
    }


@immutable
class EDTFDateTime(_EDTFComparable, Parseable):
    __slots__ = ("date", "hour", "minute", "second")
    date: EDTFYearMonthDay
    hour: int
    minute: int
    second: float

    __eq__ = eq_slots_noshort
    __hash__ = hash_slots

    @property
    def year(self) -> int:
        return self.date.year

    @property
    def month(self) -> Month:
        return self.date.month

    @property
    def day(self) -> int:
        return self.date.day

    @property
    def year_qualifier(self) -> Qualifier:
        return self.date.year_qualifier

    @property
    def month_qualifier(self) -> Qualifier:
        return self.date.month_qualifier

    @property
    def day_qualifier(self) -> Qualifier:
        return self.date.day_qualifier

    @property
    def time(self) -> dt.time:
        return self.to_datetme().time()

    def seconds_from_midnight(self) -> float:
        return fma(self.hour, 60, fma(self.minute, 60, self.second))

    @classmethod
    def from_datetime(cls, datetime: dt.datetime, /) -> Self:
        if datetime.utcoffset() is not None:
            raise ValueError("Aware datetime for non-offset EDTF date-time")
        return cls(
            datetime.year,
            datetime.month,
            datetime.day,
            datetime.hour,
            datetime.minute,
            (datetime.second + datetime.microsecond / 1000000),
        )

    def to_datetme(self) -> dt.datetime:
        s = int(self.second)
        us = int((self.second - s) * 1000000)
        return dt.datetime.combine(
            self.date.to_datetime(), dt.time(self.hour, self.minute, s, us)
        )

    def __new__(
        cls,
        year: int,
        month: Month | int,
        day: Day1Based,
        hour: int,
        minute: int,
        second: float,
        *,
        year_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
        month_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
        day_qualifier: Qualifier | str = Qualifier.UNQUALIFIED,
    ) -> Self:
        date = EDTFYearMonthDay(
            year,
            month,
            day,
            year_qualifier=year_qualifier,
            month_qualifier=month_qualifier,
            day_qualifier=day_qualifier,
        )
        if not 0 <= hour < 24:
            raise ValidityError(f"Hour out of range: {hour!r}")
        if not 0 <= minute < 60:
            raise ValidityError(f"Minute out of range: {hour!r}")
        if not 0 <= second < 60:
            raise ValidityError(f"Second out of range: {hour!r}")
        return new_with_fields(cls, date=date, hour=hour, minute=minute, second=second)

    __repr__ = repr_slots

    def __str__(self) -> str:
        return f"{self.date!s}T{self.hour:02d}:{self.minute:02d}:{format_time_component(self.second)}"

    @classmethod
    def parse(cls, source: str, /) -> Self:
        return cls(**_edtf_dt_parse(source))

    def _compare_key(self) -> tuple[DateKey, DateKey]:
        start = (self.year, self.month, self.day, self.hour, self.minute, self.second)
        return start, start


@immutable
class EDTFOffsetDateTime(Parseable):
    __slots__ = (
        "year",
        "month",
        "day",
        "year_qualifier",
        "month_qualifier",
        "day_qualifier",
        "hour",
        "minute",
        "second",
        "offset_seconds",
    )

    year: int
    month: Month
    day: Day1Based
    year_qualifier: Qualifier
    month_qualifier: Qualifier
    day_qualifier: Qualifier
    hour: int
    minute: int
    second: float
    offset_seconds: float

    @property
    def epoch_seconds(self) -> float:
        # Epoch seconds doesn't take leap seconds into account
        return epoch_seconds(
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.offset_seconds,
        )

    # NOTE: __eq__ and __hash__ are stricter than __lt__, __le__, __ge__ and __gt__
    # as the former two also check for offset and qualifiers.
    # Offset date-time only compares with the same type of dt.datetime.
    __lt__, __le__, _, __ge__, __gt__, _ = make_compare_fns(
        lambda self: self.epoch_seconds
    )

    __eq__ = eq_slots_noshort
    __hash__ = hash_slots
    __repr__ = repr_slots

    def __new__(
        cls,
        year: int,
        month: int,
        day: Day1Based,
        hour: int,
        minute: int,
        second: float,
        offset_seconds: float,
        *,
        year_qualifier: Qualifier = Qualifier.UNQUALIFIED,
        month_qualifier: Qualifier = Qualifier.UNQUALIFIED,
        day_qualifier: Qualifier = Qualifier.UNQUALIFIED,
    ) -> Self:
        # XXX: RFC 3339 says something about "-00:00", which is subtly different from "Z"/"+00:00"
        # ISO 8601 doesn't do this, and neither does TC39 nor EDTF
        month = Month(month)
        if not 1 <= day <= days_in_month(year, month):
            raise ValidityError(f"Day out of range: {day!r}")
        if hour == 24 and minute == 0 and second == 0:
            # End of day
            pass
        else:
            if not 0 <= hour < 24:
                raise ValidityError(f"Hour out of range: {hour!r}")
            if not 0 <= minute < 60:
                raise ValidityError(f"Minute out of range: {minute!r}")
            if not 0 <= second < 60:
                # XXX:
                # None of the existing implementations of ISO 8601 (including TC39) supports leap seconds.
                # There being no shared semantics out there, we don't support it either
                raise ValidityError(f"Second out of range: {second!r}")
        if offset_seconds == -0.0:
            offset_seconds = 0.0
        if not -86400 < offset_seconds < 86400:
            raise ValidityError(f"Offset out of range: {offset_seconds!r}")
        return new_with_fields(
            cls,
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            offset_seconds=offset_seconds,
            year_qualifier=year_qualifier,
            month_qualifier=month_qualifier,
            day_qualifier=day_qualifier,
        )

    def __str__(self) -> str:
        if self.offset_seconds == 0:
            offset_str = "Z"
        else:
            offset_m, offset_s = divmod(abs(self.offset_seconds), 60)
            offset_h, offset_m = divmod(offset_m, 60)
            if offset_s:
                offset_str = f"{int(offset_h):02d}:{int(offset_m):02d}:{format_time_component(offset_s)}"
            else:
                offset_str = f"{int(offset_h):02d}:{int(offset_m):02d}"
            if self.offset_seconds > 0:
                offset_str = "+" + offset_str
            else:
                offset_str = "-" + offset_str
        if self.second:
            second_str = f":{format_time_component(self.second)}"
        else:
            second_str = ""
        date_str = _edtf_ymd_str(
            self.year,
            self.month,
            self.day,
            self.year_qualifier,
            self.month_qualifier,
            self.day_qualifier,
        )
        return f"{date_str}T{self.hour:02d}:{self.minute:02d}{second_str}{offset_str}"

    @classmethod
    def parse(cls, source: str, /) -> Self:
        if source.upper().endswith("Z"):
            offset_seconds = 0
            dt_part = source[:-1]
        else:
            sign = 1
            dt_part, plus, offset_part = source.rpartition("+")
            if not plus:
                sign = -1
                dt_part, minus, offset_part = source.rpartition("-")
            f = TIME_PATTERN.fullmatch(offset_part)
            if f is None:
                raise WellFormednessError(
                    f"Source cannot be parsed as an offset date-time: {source!r}"
                )
            gd = f.groupdict()
            oh = float(gd["h"])
            try:
                om = float(gd["m"])
            except TypeError, ValueError:
                om = 0.0
            try:
                os = float(gd["s"])
            except TypeError, ValueError:
                os = 0.0
            offset_seconds = copysign(oh * 3600 + om * 60 + os, sign)
        dt = _edtf_dt_parse(dt_part)
        return cls(**dt, offset_seconds=offset_seconds)

    @classmethod
    def from_datetime(cls, datetime: dt.datetime, /) -> Self:
        if datetime.tzinfo is None:
            raise ValueError("No timezone for offset date-time")
        offset = datetime.utcoffset()
        if offset is None:
            raise ValueError("No UTC offset for timezone")
        return cls(
            datetime.year,
            datetime.month,
            datetime.day,
            datetime.hour,
            datetime.minute,
            datetime.second + datetime.microsecond / 1000000,
            offset_seconds=offset.total_seconds(),
        )

    def to_datetime(self) -> dt.datetime:
        s = int(self.second)
        us = int((self.second - s) * 1000000)
        return dt.datetime(
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            s,
            us,
            tzinfo=dt.timezone(dt.timedelta(seconds=self.offset_seconds)),
        )


def _process_end_components(start, s) -> EDTFDate:
    try:
        return EDTFDate.parse(s)
    except ValueError as ve:
        md = MONTH_DAY_PATTERN.fullmatch(s)
        if md is not None:
            md_gd = md.groupdict()
            mq = (
                Qualifier(md_gd["mq"])
                | Qualifier(md_gd["ymq"])
                | Qualifier(md_gd["ymdq"])
            )
            dq = Qualifier(md_gd["dq"]) | Qualifier(md_gd["ymdq"])
            month = int10(md_gd["month"])
            day = int10(md_gd["day"])
            match start:
                case EDTFYear() | EDTFYearMonth() | EDTFYearMonthDay():
                    return EDTFYearMonthDay(
                        start.year,
                        month,
                        day,
                        year_qualifier=start.year_qualifier,
                        month_qualifier=mq,
                        day_qualifier=dq,
                    )
                case _:
                    raise WellFormednessError(
                        "Partial end components with no corresponding start informationi in EDTF interval"
                    )
        else:
            lc = LAST_COMPONENT_PATTERN.fullmatch(s)
            if lc is None:
                raise ve
            lc_gd = lc.groupdict()
            l = int10(lc_gd["day"])
            lcq = Qualifier(lc_gd["dq"]) | Qualifier(lc_gd["ymdq"])
            match start:
                case EDTFYear() | EDTFYearMonth():
                    return EDTFYearMonth(
                        start.year,
                        l,
                        year_qualifier=start.year_qualifier,
                        month_qualifier=lcq,
                    )
                case EDTFYearMonthDay():
                    return EDTFYearMonthDay(
                        start.year,
                        start.month,
                        l,
                        year_qualifier=start.year_qualifier,
                        month_qualifier=start.month_qualifier,
                        day_qualifier=lcq,
                    )
                case _:
                    raise WellFormednessError(
                        "Partial end components with no corresponding start informationi in EDTF interval"
                    )


@runtime_final
@immutable
class EDTFInterval(_EDTFComparable, Parseable):
    __slots__ = ("start", "end")

    # NOTE: As per spec, EDTF Interval does not support time of day (but biblatex does unfortunately!)
    start: EDTFDate | EDTFDateTime | Open | None
    end: EDTFDate | EDTFDateTime | Open | None

    def __new__(
        cls,
        start: EDTFDate | EDTFDateTime | Open | None,
        end: EDTFDate | EDTFDateTime | Open | None,
    ) -> Self:
        if isinstance(start, (EDTFDate, EDTFDateTime)) and isinstance(
            end, (EDTFDate, EDTFDateTime)
        ):
            if start > end:
                start, end = end, start
        return new_with_fields(cls, start=start, end=end)

    def __str__(self) -> str:
        match self.start:
            case EllipsisType():
                start_str = ".."
            case None:
                start_str = ""
            case _:
                start_str = str(self.start)
        match self.end:
            case EllipsisType():
                end_str = ".."
            case None:
                end_str = ""
            case _:
                end_str = str(self.end)
        return f"{start_str}/{end_str}"

    __repr__ = repr_slots

    @classmethod
    def parse(cls, source: str, /) -> Self:
        start_str, slash, end_str = source.partition("/")
        if not slash:
            start_str, double_hyphen, end_str = source.partition("--")
            if not double_hyphen:
                raise WellFormednessError(
                    f"Source cannot be parsed as EDTF interval: {source!r}"
                )
        match start_str:
            case "..":
                start = Ellipsis
            case "":
                start = None
            case s:
                start = EDTFDate.parse(s)
        match end_str:
            case "..":
                end = Ellipsis
            case "":
                end = None
            case s:
                end = _process_end_components(start, end_str)
        return cls(start, end)

    def _compare_key(self) -> tuple[DateKey | Open | None, DateKey | Open | None]:
        start = self.start
        if isinstance(start, (EDTFDate, EDTFDateTime)):
            start = start._compare_key()[0]
        end = self.end
        if isinstance(end, (EDTFDate, EDTFDateTime)):
            end = end._compare_key()[1]
        return start, end
