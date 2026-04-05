import re
from enum import StrEnum
from math import (
    atan,
    atan2,
    cos,
    degrees,
    isclose,
    log,
    pi,
    radians,
    sin,
    sqrt,
    tan,
    tau,
)
from typing import Final, Literal, Self
from urllib.parse import SplitResult, urlsplit

from ..util.functions import (
    eq_slots,
    hash_slots,
    immutable,
    new_with_fields,
    runtime_final,
)
from ..util.number import HALF_PI, adjust_decimal_places, to_decimal_places
from ..util.parse import Parseable, ValidityError, WellFormednessError
from ..util.uri import PCT_ENCODED
from .urn import URN

# WGS84 constants
#: Equatorial radius in meters, defined in WGS84
WGS84_SEMI_MAJOR_AXIS = 6378137.0  # meters
#: 1 / flattening, defined in WGS84
WGS84_INVERSE_FLATTENING = 298.257223563

# Constants rarely used, but appear in Sandwell (2002)
#: Rate of rotation in radians per second, defined in WGS84
WGS84_ROTATION_RATE = 7.292115e-5  # rad/s
#: Product of gravitational constant G and Earth's mass M, defined in WGS84
WGS84_GM = 3.986004418e14  # N m^2/kg

# Derived constants
#: 1 - axis ratio, equal to 0.0033528106647474805
WGS84_FLATTENING = 1 / WGS84_INVERSE_FLATTENING
#: Ratio between semi-minor axis and semi-major axis, equal to 0.996647
WGS84_AXIS_RATIO = 1 - WGS84_FLATTENING
#: Polar radius, equal to 6356752.3142 meters
WGS84_SEMI_MINOR_AXIS = WGS84_SEMI_MAJOR_AXIS * WGS84_AXIS_RATIO
#: Square of first eccentricity, equal to 0.00669438
WGS84_FIRST_ECCENTRICITY_SQUARED = (2 - WGS84_FLATTENING) * WGS84_FLATTENING
#: First eccentricity, equal to 0.081819191
WGS84_FIRST_ECCENTRICITY = sqrt(WGS84_FIRST_ECCENTRICITY_SQUARED)
#: Mean radius of the Earth, equal to 6371008.7714 m
WGS84_MEAN_RADIUS = (2 * WGS84_SEMI_MAJOR_AXIS + WGS84_SEMI_MINOR_AXIS) / 3
#: Dynamic form factor, equal to 1.081874E-3
WGS84_J2 = (
    2 * WGS84_FLATTENING
    - (WGS84_SEMI_MAJOR_AXIS**3) * (WGS84_ROTATION_RATE**2) / WGS84_GM
) / 3

# 2*pi*a^2+pi*(b*2/e)ln[(1+e)/(1–e)]
#: Surface area of the Earth, equal to 5.10065621724E+14 m^2
WGS84_SURFACE_AREA = 2 * pi * (WGS84_SEMI_MAJOR_AXIS**2) + pi * (
    (WGS84_SEMI_MINOR_AXIS**2) / WGS84_FIRST_ECCENTRICITY
) * log((1 + WGS84_FIRST_ECCENTRICITY) / (1 - WGS84_FIRST_ECCENTRICITY))

# 4*pi*a^2*b/3
#: Volume of the Earth, equal to 1.083207319801E+21 m^3
WGS84_VOLUME = 4 * pi * (WGS84_SEMI_MAJOR_AXIS**2) * WGS84_SEMI_MINOR_AXIS / 3

# A constant factor used in geodesic calculations
_aabbbb = (
    (WGS84_SEMI_MAJOR_AXIS + WGS84_SEMI_MINOR_AXIS)
    * (WGS84_SEMI_MAJOR_AXIS - WGS84_SEMI_MINOR_AXIS)
    / WGS84_SEMI_MINOR_AXIS**2
)


# Equations from
# Sandwell (2002) Reference Earth Model - WGS84
# https://topex.ucsd.edu/geodynamics/14gravity1_2.pdf
def geographic_to_geocentric(geographic_latitude_deg: float) -> float:
    # By convention, geographic latitude is in degrees, geocentric is in radians
    if -90 < geographic_latitude_deg < 90:
        return atan((WGS84_AXIS_RATIO**2) * tan(radians(geographic_latitude_deg)))
    elif geographic_latitude_deg == 90:
        return HALF_PI
    elif geographic_latitude_deg == -90:
        return -HALF_PI
    raise ValueError(
        f"Geographic latitude must be between -90 and 90 degrees inclusive, got {geographic_latitude_deg!r}"
    )


def geocentric_to_geographic(geocentric_latitude: float) -> float:
    # By convention, geographic latitude is in degrees, geocentric is in radians
    if -HALF_PI < geocentric_latitude < HALF_PI:
        return degrees(atan(tan(geocentric_latitude) / (WGS84_AXIS_RATIO**2)))
    elif geocentric_latitude == HALF_PI:
        return 90
    elif geocentric_latitude == -HALF_PI:
        return -90
    raise ValueError(
        f"Geocentric latitude must be between -pi/2 and pi/2 inclusive, got {geocentric_latitude!r}"
    )


def radius_of_spheroid(geocentric_latitude: float) -> float:
    if -HALF_PI < geocentric_latitude < HALF_PI:
        return 1 / sqrt(
            (cos(geocentric_latitude) / WGS84_SEMI_MAJOR_AXIS) ** 2
            + (sin(geocentric_latitude) / WGS84_SEMI_MINOR_AXIS) ** 2
        )
        # or
        # return WGS84_SEMI_MAJOR_AXIS*(1-WGS84_FLATTENING*(sin(geocentric_latitude)**2))
    elif geocentric_latitude in (HALF_PI, -HALF_PI):
        return WGS84_SEMI_MINOR_AXIS
    raise ValueError(
        f"Geocentric latitude must be between -pi/2 and pi/2 inclusive, got {geocentric_latitude!r}"
    )


# The standard ever only supports one projection system, but here we go...
class Projection(StrEnum):
    WGS84 = "wgs84"


# The ABNF in RFC 5870 is slightly different from that in other RFCs (such as RFC 3986)
# Notably, the "unreserved" production here contains some additional marks not in 3986!
ALPHANUM = r"[0-9A-Za-z]"
PNUM = r"\d+(\.\d+)?"
NUM = rf"-?{PNUM}"
MARK = r"[-_.!~*'()]"
GEO_UNRESERVED = rf"{ALPHANUM}|{MARK}"
P_UNRESERVED = r"[\[\]:&+$]"
LABELTEXT = r"[\-0-9A-Za-z]+"
PARAMCHAR = rf"{P_UNRESERVED}|{GEO_UNRESERVED}|{PCT_ENCODED}"
CRSP = rf";crs=(?P<CRSLABEL>wgs84|{LABELTEXT})"
UNCP = rf";u=(?P<UVAL>{PNUM})"
PARAMETERS = rf";{LABELTEXT}(=({PARAMCHAR})+)?"

COORDINATES = rf"(?P<COORD_A>{NUM}),(?P<COORD_B>{NUM})(,(?P<COORD_C>{NUM}))?"
GEO_PATH = rf"{COORDINATES}({CRSP})?({UNCP})?(?P<PARAMS>({PARAMETERS})*)"
GEO_PATTERN = re.compile(GEO_PATH, re.ASCII | re.IGNORECASE)
NUM_PATTERN = re.compile(NUM, re.ASCII | re.IGNORECASE)


def _parse_num(s: str) -> float:
    try:
        if NUM_PATTERN.fullmatch(s):
            return float(s)
        raise ValueError
    except ValueError:
        raise WellFormednessError(f"Source Geo URI contains malformed number: {s!r}")


DEFAULT_MAX_ITERATIONS = 20
DEFAULT_RELATIVE_TOLERANCE = 1e-9
DEFAULT_ABSOLUTE_TOLERANCE = 0.0


def geodesic_distance_bearings_radians(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE,
) -> tuple[float, float, float, int]:
    """Calculates the approximate length of the geodesic between two points on the ellipsoid surface.
    All angles are in radians. Distance is in meters.
    The keyword-only arguments control the number of iterations as well as convergence.
    The relative and absolute tolerances are passed to `math.isclose()` to determine when iteration should end.

    :returns: A 4-tuple of `(distance, alpha1, alpha2, iterations)`. If the two points are the same, return a 4-tuple of zeros.
    """
    # "Difference in longitude, positive east"
    if not -HALF_PI <= latitude1 <= HALF_PI:
        raise ValueError(f"latitude1 absolute value not <= pi/2: {latitude1!r}")
    if not -HALF_PI <= latitude2 <= HALF_PI:
        raise ValueError(f"latitude2 absolute value not <= pi/2: {latitude2!r}")
    if not -pi <= longitude1 <= pi:
        raise ValueError(f"longitude1 absolute value not <= pi: {longitude1!r}")
    if not -pi <= longitude2 <= pi:
        raise ValueError(f"longitude2 absolute value not <= pi: {longitude2!r}")

    if latitude1 == latitude2 and longitude1 == longitude2:
        return 0.0, 0.0, 0.0, 0

    L = longitude2 - longitude1

    U1 = atan(WGS84_AXIS_RATIO * tan(latitude1))
    U2 = atan(WGS84_AXIS_RATIO * tan(latitude2))

    # Since U1 and U2 are given, we can safely store the values of their sine and cosine
    sU1 = sin(U1)
    cU1 = cos(U1)
    sU2 = sin(U2)
    cU2 = cos(U2)
    cU1sU2 = cU1 * sU2
    sU1cU2 = sU1 * cU2
    sU1sU2 = sU1 * sU2
    cU1cU2 = cU1 * cU2

    # first approximation
    lamb = L
    A = B = 0
    i = 0
    slamb = clamb = csigma = ssigma = salpha = sigma = -1
    for _ in range(max(max_iterations, 1)):
        slamb = sin(lamb)
        clamb = cos(lamb)
        ssigma = sqrt((cU2 * slamb) ** 2 + (cU1sU2 - sU1cU2 * clamb) ** 2)
        csigma = sU1sU2 + cU1cU2 * clamb
        # tsigma = ssigma / csigma
        sigma = atan2(ssigma, csigma)
        salpha = cU1cU2 * slamb / ssigma
        csqalpha = 1 - salpha**2
        if csqalpha == 0:
            c2sigma_m = 0
            C = 0
        else:
            c2sigma_m = csigma - 2 * sU1sU2 / csqalpha
            # 10
            C = (
                WGS84_FLATTENING
                * csqalpha
                * (4 + WGS84_FLATTENING * (4 - 3 * csqalpha))
                / 16
            )
        lamb_new = L + (1 - C) * WGS84_FLATTENING * salpha * (
            sigma + C * ssigma * (c2sigma_m + C * csigma * (2 * c2sigma_m**2 - 1))
        )
        usq = csqalpha * _aabbbb

        # We use the 3a, 4a and 6a approximations to simplify calculations (avoids nested iterations)
        # A = 1 + usq / 256 * (64 + usq * (5 * usq - 12))
        # B = usq / 512 * (128 + usq * (37 * usq - 64))

        # A further simplification in 1976
        # See https://en.wikipedia.org/wiki/Vincenty%27s_formulae
        up = sqrt(usq + 1)
        k1 = (up - 1) / (up + 1)
        A = (1 + k1**2 / 4) / (1 - k1)
        B = k1 * (1 - 3 * k1**2 / 8)

        if isclose(
            lamb_new, lamb, rel_tol=relative_tolerance, abs_tol=absolute_tolerance
        ):
            lamb = lamb_new
            break
        else:
            lamb = lamb_new
            i += 1

    deltasigma = B * ssigma * (c2sigma_m + B * csigma * (2 * c2sigma_m**2 - 1) / 4)
    distance = WGS84_SEMI_MINOR_AXIS * A * (sigma - deltasigma)
    alpha1 = atan2(cU2 * slamb, cU1sU2 - sU1cU2 * clamb)
    if alpha1 < 0:
        alpha1 += tau
    alpha2 = atan2(cU1 * slamb, cU1sU2 * clamb - sU1cU2)
    if alpha2 < 0:
        alpha2 += tau

    return (
        float(distance),
        alpha1,
        alpha2,
        i,
    )


def geodesic_distance_bearings_degrees(
    latitude1_deg: float,
    longitude1_deg: float,
    latitude2_deg: float,
    longitude2_deg: float,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE,
) -> tuple[float, float, float, int]:
    """Degree version of the similarly named function."""
    d, a1, a2, i = geodesic_distance_bearings_radians(
        radians(latitude1_deg),
        radians(longitude1_deg),
        radians(latitude2_deg),
        radians(longitude2_deg),
        max_iterations=max_iterations,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    )
    return d, degrees(a1), degrees(a2), i


@immutable
class GeoPoint(Parseable):
    __slots__ = ("coord_a", "coord_b", "coord_c", "uncertainty", "crs")
    #: WGS84 Latitude
    coord_a: float
    #: WGS84 Longitude
    coord_b: float
    #: Height above WGS84 geoid (this is not equivalent to the sea level), or None
    coord_c: float | None
    #: Uncertainty in meters, or unspecified
    uncertainty: float | None

    # Can be overridden by subclasses
    crs: Projection

    __match_args__ = ("coord_a", "coord_b", "coord_c", "uncertainty", "crs")

    def __new__(
        cls,
        coord_a: float,
        coord_b: float,
        coord_c: float | None = None,
        uncertainty: float | None = None,
        crs: Projection = Projection.WGS84,
    ):
        """Subclasses that implement specific CRS should not call GeoPoint.__new__,
        but instead create their own instances.
        """

        if uncertainty is not None and uncertainty < 0:
            raise ValidityError(f"Uncertainty must be non-negative: {uncertainty}")

        # XXX: if other projection systems do become available,
        # we will need dispatch logic for other subclasses
        if not crs or crs.casefold() == Projection.WGS84:
            return WGS84Point(coord_a, coord_b, coord_c, uncertainty=uncertainty)

        return new_with_fields(
            GeoPoint,
            cls,
            coord_a=coord_a,
            coord_b=coord_b,
            coord_c=coord_c,
            uncertainty=uncertainty,
            crs=Projection(crs.casefold()),
        )

    def __str__(self) -> str:
        a, b = adjust_decimal_places(self.coord_a, self.coord_b)
        s = f"{a},{b}"
        if self.coord_c is not None:
            s = f"{s},{to_decimal_places(self.coord_c)}"
        if self.crs != Projection.WGS84:
            s = f"{s};crs={self.crs!s}"
        if self.uncertainty is not None:
            s = f"{s};u={to_decimal_places(self.uncertainty)}"
        return f"geo:{s}"

    def to_wgs84(self) -> WGS84Point:
        raise NotImplementedError

    @classmethod
    def parse(cls, source: str | SplitResult, /) -> Self:
        if isinstance(source, str):
            source = urlsplit(source)
        if source.scheme.casefold() != "geo":
            raise WellFormednessError(
                f'Geo URI must have a "geo:" scheme, got {source.scheme!r}'
            )

        m = GEO_PATTERN.fullmatch(source.path)
        if m is not None:
            # Groups:
            # latitude, longitude, [altitude] [;crsp=CRSLABEL] [;u=UVAL] PARAMS
            # The regular expression (almost) guarantees the strings passed to float() are well-formed
            # We wrangle with floating point oddities (negative zeroes) in the constructor, not here

            # NOTE: Encoding considerations
            # The ABNF forbids allow coordinates, crs and uncertainty to be percent-encoded,
            # while the text of the RFC states: "It is RECOMMENDED that for readability the contents of
            # <COORD_a>, <COORD_b>, and <COORD_c> as well as <crslabel> and <uval> are never percent-encoded."

            # We consider the ABNF grammar to be authoritative,
            # and percent-encoding to be an error rather than a non-recommendation.

            a = _parse_num(m["COORD_A"])
            b = _parse_num(m["COORD_B"])
            altitude = m["COORD_C"]
            c = _parse_num(altitude) if altitude is not None else None
            crslabel = m["CRSLABEL"]
            crs = (
                Projection(crslabel.casefold())
                if crslabel is not None
                else Projection.WGS84
            )
            uval = m["UVAL"]
            u = _parse_num(uval) if uval is not None else None
            return cls(a, b, c, uncertainty=u, crs=crs)
        raise WellFormednessError(f"Source cannot be parsed as Geo URI: {source!r}")

    __eq__ = eq_slots
    __hash__ = hash_slots

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}"
            f"({self.coord_a!r}, {self.coord_b!r}"
            + ("" if self.coord_c is None else f", {self.coord_c!r}")
            + (
                ""
                if self.uncertainty is None
                else f", uncertainty={self.uncertainty!r}"
            )
            + ("" if self.crs == Projection.WGS84 else f", crs={self.crs!r}")
            + ")"
        )


GRS4326 = URN.parse("urn:ogc:def:crs:EPSG:4326")
GRS4979 = URN.parse("urn:ogc:def:crs:EPSG:4979")


@runtime_final
@immutable
class WGS84Point(GeoPoint):
    #: Coordinate Reference System, currently only "wgs84" is defined
    crs: Final[Projection] = Projection.WGS84

    @property
    def latitude(self) -> float:
        return self.coord_a

    @property
    def longitude(self) -> float:
        return self.coord_b

    @property
    def altitude(self) -> float | None:
        return self.coord_c

    def __new__(
        cls,
        latitude: float,
        longitude: float,
        altitude: float | None = None,
        uncertainty: float | None = None,
        crs: Literal[Projection.WGS84] = Projection.WGS84,
    ):
        if crs != Projection.WGS84:
            raise ValueError("Not a WGS84 coordinate")

        #  RFC 5870 3.4.2:
        #    'geo' URIs with longitude values outside the range of -180 to 180
        #     decimal degrees or with latitude values outside the range of -90 to
        #     90 degrees MUST be considered invalid.
        if not -90 <= latitude <= 90:
            raise ValidityError(
                f"Latitude must be between -90 and 90 inclusive: {latitude}"
            )
        if not -180 <= longitude <= 180:
            raise ValidityError(
                f"Longitude must be between -180 and 180 inclusive: {longitude}"
            )

        # Normlize for equivalence
        # The <longitude> of coordinate values reflecting the poles (<latitude>
        #    set to -90 or 90 degrees) SHOULD be set to "0", although consumers of
        #    'geo' URIs MUST accept such URIs with any longitude value from -180
        #    to 180.

        # The value of "-0" for <num> is allowed and is identical to "0".

        # For the default CRS of WGS-84, the following comparison rules apply
        # additionally:
        # o  Where <latitude> of a 'geo' URI is set to either 90 or -90
        #     degrees, <longitude> MUST be ignored in comparison operations
        #     ("poles case").
        # o  A <longitude> of 180 degrees MUST be considered equal to
        #     <longitude> of -180 degrees for the purpose of URI comparison
        #     ("date line" case).

        if latitude == 90 or latitude == -90:
            # Poles case
            longitude = 0.0
        elif latitude == -0.0:
            # Negative zero
            latitude = 0.0

        if longitude == -180:
            # Date line case
            longitude = 180.0
        elif longitude == -0.0:
            # Negative zero
            longitude = 0.0
        if altitude == -0.0:
            # Negative zero
            altitude = 0.0

        if uncertainty is not None and not uncertainty >= 0:
            raise ValidityError(f"Uncertainty must be non-negative: {uncertainty}")

        return new_with_fields(
            GeoPoint,
            cls,
            coord_a=latitude,
            coord_b=longitude,
            coord_c=altitude,
            uncertainty=uncertainty,
            crs=Projection.WGS84,
        )

    def distance_bearings(
        self,
        dest: Self,
        *,
        max_iter: int = DEFAULT_MAX_ITERATIONS,
        rel_tol: float = DEFAULT_RELATIVE_TOLERANCE,
        abs_tol: float = DEFAULT_ABSOLUTE_TOLERANCE,
    ) -> tuple[float, float, float, int]:
        """Calculates the approximate length of the geodesic between two points on the ellipsoid surface.
        See `geodesic_distance_bearings_degrees` for the returned value.

        :returns: A 4-tuple of `(distance, alpha1, alpha2, iterations)`, in degrees.
        """
        if self == dest:
            return 0.0, 0.0, 0.0, 0
        return geodesic_distance_bearings_degrees(
            self.latitude,
            self.longitude,
            dest.latitude,
            dest.longitude,
            max_iterations=max_iter,
            relative_tolerance=rel_tol,
            absolute_tolerance=abs_tol,
        )

    def to_wgs84(self) -> WGS84Point:
        return self

    @property
    def crs_definition(self) -> URN:
        if self.altitude is None:
            return GRS4326
        return GRS4979
