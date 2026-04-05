# SPDX-License-Identifier: MIT

import unittest

# 100 meters
MAX_DELTA = 0.1
# 0.1 degrees
MAX_DELTA_ANGLE = 0.1


CITIES = {
    "North Pole": (90.0, 0.0),
    "South Pole": (-90.0, 0.0),
    "NYC": (40.712778, -74.006111),
    "Rio": (-22.911111, -43.205556),
    "Tokyo": (35.658514, 139.70133),
    "Sydney": (-33.85681, 151.21514),
}

# Given values of test cases are calculated with https://geodesyapps.ga.gov.au/vincenty-batch-processing

CITY_PAIRS_CSV = """North Pole,90.0,0.0,South Pole,-90.0,0.0,20003931.459,180.000000,360.000000
North Pole,90.0,0.0,NYC,40.712778,-74.006111,5493288.767,254.006111,0.000000
North Pole,90.0,0.0,Rio,-22.911111,-43.205556,12536659.439,223.205556,0.000000
North Pole,90.0,0.0,Tokyo,35.658514,139.70133,6054312.925,40.298670,360.000000
North Pole,90.0,0.0,Sydney,-33.85681,151.21514,13749744.380,28.784860,360.000000
South Pole,-90.0,0.0,North Pole,90.0,0.0,20003931.459,0.000000,180.000000
South Pole,-90.0,0.0,NYC,40.712778,-74.006111,14510642.692,285.993889,180.000000
South Pole,-90.0,0.0,Rio,-22.911111,-43.205556,7467272.020,316.794444,180.000000
South Pole,-90.0,0.0,Tokyo,35.658514,139.70133,13949618.534,139.701330,180.000000
South Pole,-90.0,0.0,Sydney,-33.85681,151.21514,6254187.079,151.215140,180.000000
NYC,40.712778,-74.006111,North Pole,90.0,0.0,5493288.767,0.000000,254.006111
NYC,40.712778,-74.006111,South Pole,-90.0,0.0,14510642.692,180.000000,285.993889
NYC,40.712778,-74.006111,Rio,-22.911111,-43.205556,7731520.852,149.695553,335.441845
NYC,40.712778,-74.006111,Tokyo,35.658514,139.70133,10875541.794,332.981345,25.082408
NYC,40.712778,-74.006111,Sydney,-33.85681,151.21514,15986957.755,266.264842,65.668501
Rio,-22.911111,-43.205556,North Pole,90.0,0.0,12536659.439,0.000000,223.205556
Rio,-22.911111,-43.205556,South Pole,-90.0,0.0,7467272.020,180.000000,316.794444
Rio,-22.911111,-43.205556,NYC,40.712778,-74.006111,7731520.852,335.441845,149.695553
Rio,-22.911111,-43.205556,Tokyo,35.658514,139.70133,18564174.659,349.738031,11.644231
Rio,-22.911111,-43.205556,Sydney,-33.85681,151.21514,13539916.054,194.004962,164.437558
Tokyo,35.658514,139.70133,North Pole,90.0,0.0,6054312.925,360.000000,40.298670
Tokyo,35.658514,139.70133,South Pole,-90.0,0.0,13949618.534,180.000000,139.701330
Tokyo,35.658514,139.70133,NYC,40.712778,-74.006111,10875541.794,25.082408,332.981345
Tokyo,35.658514,139.70133,Rio,-22.911111,-43.205556,18564174.659,11.644231,349.738031
Tokyo,35.658514,139.70133,Sydney,-33.85681,151.21514,7788208.727,169.810767,350.032000
Sydney,-33.85681,151.21514,North Pole,90.0,0.0,13749744.380,360.000000,28.784860
Sydney,-33.85681,151.21514,South Pole,-90.0,0.0,6254187.079,180.000000,151.215140
Sydney,-33.85681,151.21514,NYC,40.712778,-74.006111,15986957.755,65.668501,266.264842
Sydney,-33.85681,151.21514,Rio,-22.911111,-43.205556,13539916.054,164.437558,194.004962
Sydney,-33.85681,151.21514,Tokyo,35.658514,139.70133,7788208.727,350.032000,169.810767
"""


class TestGeo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global angle_difference, geodesic_distance_bearings_degrees, GeoPoint, WGS84Point
        from musculus.metadata.geo import (
            GeoPoint,
            WGS84Point,
            geodesic_distance_bearings_degrees,
        )
        from musculus.util.number import angle_difference

    def test_geodesic_degrees(self):
        for line in CITY_PAIRS_CSV.splitlines():
            city1, lat1, lon1, city2, lat2, lon2, dist, alpha1, alpha2 = line.split(",")
            d, a, b, _ = geodesic_distance_bearings_degrees(
                float(lat1),
                float(lon1),
                float(lat2),
                float(lon2),
            )
            self.assertAlmostEqual(d, float(dist), delta=MAX_DELTA)
            if city1.endswith("Pole") and city2.endswith("Pole"):
                # No azimuths between the poles
                continue

            self.assertLessEqual(
                abs(angle_difference(a, float(alpha1))),
                MAX_DELTA_ANGLE,
            )
            # The third given value in our test case is the "reverse azimuth"
            self.assertLessEqual(
                abs(angle_difference(b, float(alpha2) + 180)),
                MAX_DELTA_ANGLE,
            )

    def test_point(self):
        cases = [
            ("geo:48.201,16.3695,183", (48.201, 16.3695, 183, None, "wgs84")),
            (
                "geo:48.198634,16.371648;crs=wgs84;u=40",
                (
                    48.198634,
                    16.371648,
                    None,
                    40,
                    "wgs84",
                ),
            ),  # Karlsruhe
        ]
        for uri, (lat, lon, alt, u, crs) in cases:
            geo = GeoPoint.parse(uri)
            # self.assertIsInstance(geo, WGS84Point)
            assert isinstance(geo, WGS84Point)
            self.assertEqual(geo.latitude, lat)
            self.assertEqual(geo.longitude, lon)
            self.assertEqual(geo.altitude, alt)
            self.assertEqual(geo.uncertainty, u)
            self.assertEqual(geo.crs, crs)

    def test_equivalence(self):
        cases = [
            ("geo:90,-22.43;crs=WGS84", "geo:90,46"),
            # XXX: spec uses semicolon for below, which is wrong!
            ("geo:22.300,-118.44", "geo:22.3,-118.4400"),
            ("geo:48.201,16.3695,183", "geo:48.201,16.3695,183;crs=wgs84"),
            ("geo:48.201,16.3695,183;u=42", "geo:48.201,16.3695,183;u=42;crs=wgs84"),
            # XXX: support custom params?
            # ("geo:66,30;u=6.500;FOo=this%2dthat", "geo:66.0,30;u=6.5;foo=this-that"),
            # ("geo:47,11;foo=blue;bar=white", "geo:47,11;bar=white;foo=blue"),
        ]
        for a, b in cases:
            geo1 = GeoPoint.parse(a)
            geo2 = GeoPoint.parse(b)
            self.assertEqual(GeoPoint.parse(str(geo1)), geo2)
            self.assertEqual(eval(repr(geo2)), geo1)
