# SPDX-License-Identifier: MIT

import copy
import pickle
import random
import unittest
from fractions import Fraction
from math import isnan


class TestRGBAColor(unittest.TestCase):
    """Many of the test cases are taken from WPT test suite `color-valid.html`."""

    @classmethod
    def setUpClass(cls):
        global RGBAColor, ChannelOrder, ColorSystem
        from musculus.metadata.color import ChannelOrder, ColorSystem, RGBAColor

    def test_construction_comparison(self):
        self.assertTrue(RGBAColor(0x00000000))
        c = RGBAColor(red=0x12, green=0x45, blue=0x89, alpha=0xF3)
        d = RGBAColor(0x12, green=0x45, blue=0x89, alpha=0xF3)
        e = RGBAColor(0x12, 0x45, blue=0x89, alpha=0xF3)
        f = RGBAColor(0x12, 0x45, 0x89, alpha=0xF3)
        g = RGBAColor(0x12, 0x45, 0x89, 0xF3)
        h = RGBAColor(rgba=0x124589F3)
        i = RGBAColor(0x124589F3)

        self.assertEqual(getattr(c, "rgba"), 0x124589F3)
        self.assertTrue(c)
        self.assertEqual(c, c)
        self.assertEqual(d, c)
        self.assertEqual(e, d)
        self.assertEqual(f, e)
        self.assertEqual(g, f)
        self.assertEqual(h, g)
        self.assertEqual(i, h)
        self.assertEqual(c.red, 0x12)
        self.assertEqual(c.green, 0x45)
        self.assertEqual(c.blue, 0x89)
        self.assertEqual(c.alpha, 0xF3)

        j = RGBAColor(red=0x12, green=0x45, blue=0x89)
        k = RGBAColor(0x12, green=0x45, blue=0x89)
        l = RGBAColor(0x12, 0x45, blue=0x89)
        m = RGBAColor(0x12, 0x45, 0x89)
        n = RGBAColor(rgba=0x124589FF)
        o = RGBAColor(0x124589FF)

        self.assertEqual(k, j)
        self.assertEqual(l, k)
        self.assertEqual(m, l)
        self.assertEqual(n, m)
        self.assertEqual(o, n)
        self.assertEqual(o.red, 0x12)
        self.assertEqual(n.green, 0x45)
        self.assertEqual(m.blue, 0x89)
        self.assertEqual(o.alpha, 0xFF)

        self.assertNotEqual(c, c.rgba)
        self.assertNotEqual(c, j)
        self.assertLess(c, j)
        self.assertLessEqual(c, j)
        self.assertLessEqual(k, j)
        self.assertGreater(j, c)
        self.assertGreaterEqual(j, c)
        self.assertGreaterEqual(j, k)
        self.assertFalse(c == j)
        self.assertFalse(j != k)
        self.assertFalse(c > j)
        self.assertFalse(c >= j)
        self.assertFalse(j < c)
        self.assertFalse(j <= c)

        # Replace
        self.assertEqual(RGBAColor(c, alpha=0xFF), j)

        with self.assertRaises(TypeError):
            j <= j.rgba  # type: ignore

    def test_pattern_matching(self):
        c = RGBAColor(0xAABBCCDD)
        match c:
            case RGBAColor(0xAABBCCDD):
                pass
            case _:
                self.fail("Positional pattern matching failed on composite RGBA value")
        match c:
            case RGBAColor(rgba=0xAABBCCDD):
                pass
            case _:
                self.fail("Keyword pattern matching failed on composite RGBA value")
        match c:
            case RGBAColor(red=0xAA, green=0xBB, blue=0xCC, alpha=0xDD):
                pass
            case _:
                self.fail("Keyword pattern matching failed on channel values")

    def test_persistence(self):
        cases = ["red", "#12FBC359"]
        for case in cases:
            color = RGBAColor.from_css(case)
            b = pickle.dumps(color)
            c = pickle.loads(b)
            d = copy.copy(color)
            e = copy.deepcopy(color)
            self.assertIsInstance(c, RGBAColor)
            self.assertEqual(c, color)
            self.assertIsInstance(d, RGBAColor)
            self.assertEqual(d, color)
            self.assertIsInstance(e, RGBAColor)
            self.assertEqual(e, color)

    def test_parse(self):
        cases = {
            "": None,
            "NONE": None,
            "transparent": "#00000000",
            "red": "#FF0000",
            "magenta": "#FF00FF",
            "#234": "#223344",
            "rgb(34, 51, 68)": "#223344",
            "rgb(254, 220, 186)": "#FeDCBa",
            "rgB(2, 3, 4)": "#020304",
            "rgb(100%, 0%, 0%)": "#FF0000",
            "rgb(255 0 0)": "#FF0000",
            "RGBA(2, 3, 4, 0.5)": "#02030480",
            "  rgBa  (  2 , 3 , 4 ,    50%   )  ": "#02030480",
        }
        locals = {"RGBAColor": RGBAColor}
        for source, hexa in cases.items():
            with self.subTest(source):
                c = RGBAColor.from_css(source, allow_none=True)
                pc = RGBAColor.parse(source, allow_none=True)
                if hexa is None:
                    self.assertIsNone(c)
                    self.assertIsNone(pc)
                    with self.assertRaises(ValueError):
                        RGBAColor(source)
                    with self.assertRaises(ValueError):
                        RGBAColor.parse(source, allow_none=False)
                    with self.assertRaises(ValueError):
                        RGBAColor.from_css(source, allow_none=False)
                    continue
                assert c is not None
                assert pc is not None
                cc = RGBAColor(source)
                hc = RGBAColor.from_hex(
                    hexa,
                    bits_per_channel=8,
                    channel_order="RGB" if len(hexa) == 7 else "RGBA",
                )
                rc = eval(repr(c), None, locals)
                self.assertIsInstance(rc, RGBAColor)
                self.assertEqual(cc, c)
                self.assertEqual(rc, c)
                self.assertEqual(hc, c)
                self.assertEqual(pc, c)
                hcf = hexa.casefold()
                self.assertEqual(str(c), hcf)
                fs = (
                    f"#{c.alpha>>4:x}{c.red>>4:x}{c.green >>4:x}{c.blue>>4:x}"
                    f"{c.alpha & 0xF:x}{c.red & 0xF:x}{c.green & 0xF:x}{c.blue & 0xF:x}"
                )
                self.assertEqual(format(c, "#argbargb"), fs)
                self.assertEqual(hash(c), hash(pc))

    def test_bpc(self):
        cases1: list[tuple[int, int, ChannelOrder]] = [
            (0x12ACEFFE, 8, "RGBA"),
            (0xFE12ACEF, 8, "ARGB"),
        ]
        c1 = RGBAColor(0x12, 0xAC, 0xEF, 0xFE)
        for i, bpc, order in cases1:
            c = RGBAColor.from_int(i, bits_per_channel=bpc, channel_order=order)
            self.assertEqual(c, c1)
            self.assertEqual(c1.to_int(bits_per_channel=bpc, channel_order=order), i)
            self.assertEqual(
                RGBAColor.from_hex(
                    f"#{i:08x}", bits_per_channel=bpc, channel_order=order
                ),
                c,
            )

        cases2: list[tuple[int, int, ChannelOrder]] = [
            (0xABCD, 4, "RGBA"),
            (0xDABC, 4, "ARGB"),
        ]
        c2 = RGBAColor(0xAABBCCDD)
        for i, bpc, order in cases2:
            c = RGBAColor.from_int(i, bits_per_channel=bpc, channel_order=order)
            self.assertEqual(c, c2)
            self.assertEqual(c2.to_int(bits_per_channel=bpc, channel_order=order), i)
            self.assertEqual(
                RGBAColor.from_hex(
                    f"#{i:04X}", bits_per_channel=bpc, channel_order=order
                ),
                c,
            )

        cases3: list[tuple[int, int, ChannelOrder]] = [
            (0x0123456789AB, 12, "RGBA"),
            (0x9AB012345678, 12, "ARGB"),
        ]
        c3 = RGBAColor(0x0134679A)
        for i, bpc, order in cases3:
            c = RGBAColor.from_int(i, bits_per_channel=bpc, channel_order=order)
            self.assertEqual(c, c3)
            self.assertEqual(
                RGBAColor.from_hex(
                    f"#{i:012x}", bits_per_channel=bpc, channel_order=order
                ),
                c,
            )

        self.assertEqual(
            c3.to_int(bits_per_channel=12, channel_order="RGBA"), 0x0103436769A9
        )
        cases4: list[tuple[int, int, ChannelOrder]] = [
            (0x7135, 4, "RGB"),
            (0x77113355, 8, "RGB"),
            (0x77911A33F550, 12, "RGB"),
        ]
        c4 = RGBAColor(0x113355FF)
        for i, bpc, order in cases4:
            c = RGBAColor.from_int(i, bits_per_channel=bpc, channel_order=order)
            self.assertEqual(c, c4)
            self.assertEqual(
                RGBAColor.from_hex(
                    "#" + (f"{i:012x}"[-bpc // 4 * 3 :]),
                    bits_per_channel=bpc,
                    channel_order=order,
                ),
                c,
            )

    def test_css_hsl(self):
        self.assertEqual(
            RGBAColor.from_css("hsl(120, 100%, 50%)"),
            RGBAColor.from_css("rgb(0, 255, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hsla(120, 100%, 50%, 0.25)"),
            RGBAColor.from_css("rgba(0, 255, 0, 0.25)"),
        )

    def test_css_out_of_range(self):
        self.assertEqual(
            RGBAColor.from_css("rgb(-2, 3, 4)"),
            RGBAColor.from_css("rgb(0, 3, 4)"),
        )
        self.assertEqual(
            RGBAColor.from_css("rgb(100, 200, 300)"),
            RGBAColor.from_css("rgb(100, 200, 255)"),
        )
        self.assertEqual(
            RGBAColor.from_css("rgb(20, 10, 0, -10)"),
            RGBAColor.from_css("rgba(20, 10, 0, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("rgb(100%, 200%, 300%)"),
            RGBAColor.from_css("rgb(255, 255, 255)"),
        )

    def test_css_hwb(self):
        self.assertEqual(
            RGBAColor.from_css("hwb(120 30% 50%)"),
            RGBAColor.from_css("rgb(77, 128, 77)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 30% 50% / 0.5)"),
            RGBAColor.from_css("rgba(77, 128, 77, 0.5)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(0 0% 0%)"),
            RGBAColor.from_css("rgb(255, 0, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 0% 0%)"),
            RGBAColor.from_css("rgb(0, 255, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(0 0% 0% / 0)"),
            RGBAColor.from_css("rgba(255, 0, 0, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 80% 0%)"),
            RGBAColor.from_css("rgb(204, 255, 204)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 0% 50%)"),
            RGBAColor.from_css("rgb(0, 128, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 30% 50% / 0)"),
            RGBAColor.from_css("rgba(77, 128, 77, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(0 100% 50% / 0)"),
            RGBAColor.from_css("rgba(170, 170, 170, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(320deg 30% 40%)"),
            RGBAColor.from_css("rgb(153, 77, 128)"),
        )

    def test_css_hwb_missing_values(self):
        self.assertEqual(
            RGBAColor.from_css("hwb(none none none)"),
            RGBAColor.from_css("rgb(255, 0, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(none none none / none)"),
            RGBAColor.from_css("rgba(255, 0, 0, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 none none)"),
            RGBAColor.from_css("rgb(0, 255, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 80% none)"),
            RGBAColor.from_css("rgb(204, 255, 204)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 none 50%)"),
            RGBAColor.from_css("rgb(0, 128, 0)"),
        )
        self.assertEqual(
            RGBAColor.from_css("hwb(120 30% 50% / none)"),
            RGBAColor.from_css("rgba(77, 128, 77, 0)"),
        )

        self.assertEqual(
            RGBAColor.from_css("hwb(none 100% 50% / none)"),
            RGBAColor.from_css("rgba(170, 170, 170, 0)"),
        )

    def test_hsl_hsv_hwb(self):
        cases = {
            "#FFD500": (
                (Fraction(71, 510) * 360, 100, 50),
                (Fraction(71, 510) * 360, 100, 100),
                (Fraction(71, 510) * 360, 0, 0),
            ),
            "#A64DFF": (
                (0.75 * 360, 100, Fraction(16600, 255)),
                (0.75 * 360, Fraction(17800, 255), 100),
                (0.75 * 360, Fraction(7700, 255), 0),
            ),
            "#A393D1": (
                (Fraction(22 * 360, 31), Fraction(3100, 77), Fraction(17800, 255)),
                (Fraction(22 * 360, 31), Fraction(6200, 209), Fraction(20900, 255)),
                (Fraction(22 * 360, 31), Fraction(4900, 85), Fraction(4600, 255)),
            ),
        }
        for color, (hsl, hsv, hwb) in cases.items():
            with self.subTest(color):
                c = RGBAColor.from_css(color)
                c1 = RGBAColor.from_model(ColorSystem.HSL, map(Fraction, hsl))
                c2 = RGBAColor.from_model(ColorSystem.HSV, map(Fraction, hsv))
                c3 = RGBAColor.from_model(ColorSystem.HWB, map(Fraction, hwb))
                self.assertEqual(c, c1)
                self.assertEqual(c, c2)
                self.assertEqual(c, c3)
                self.assertEqual(c.to_model(ColorSystem.HSL), hsl)
                self.assertEqual(c.to_model(ColorSystem.HSV), hsv)
                self.assertEqual(c.to_model(ColorSystem.HWB), hwb)

    def test_svg_names(self):
        SVG_NAMES = [
            "transparent",
            "aliceblue",
            "antiquewhite",
            "aqua",
            "aquamarine",
            "azure",
            "beige",
            "bisque",
            "black",
            "blanchedalmond",
            "blue",
            "blueviolet",
            "brown",
            "burlywood",
            "cadetblue",
            "chartreuse",
            "chocolate",
            "coral",
            "cornflowerblue",
            "cornsilk",
            "crimson",
            "cyan",
            "darkblue",
            "darkcyan",
            "darkgoldenrod",
            "darkgray",
            "darkgrey",
            "darkgreen",
            "darkkhaki",
            "darkmagenta",
            "darkolivegreen",
            "darkorange",
            "darkorchid",
            "darkred",
            "darksalmon",
            "darkseagreen",
            "darkslateblue",
            "darkslategray",
            "darkslategrey",
            "darkturquoise",
            "darkviolet",
            "deeppink",
            "deepskyblue",
            "dimgray",
            "dimgrey",
            "dodgerblue",
            "firebrick",
            "floralwhite",
            "forestgreen",
            "fuchsia",
            "gainsboro",
            "ghostwhite",
            "gold",
            "goldenrod",
            "gray",
            "grey",
            "green",
            "greenyellow",
            "honeydew",
            "hotpink",
            "indianred",
            "indigo",
            "ivory",
            "khaki",
            "lavender",
            "lavenderblush",
            "lawngreen",
            "lemonchiffon",
            "lightblue",
            "lightcoral",
            "lightcyan",
            "lightgoldenrodyellow",
            "lightgray",
            "lightgrey",
            "lightgreen",
            "lightpink",
            "lightsalmon",
            "lightseagreen",
            "lightskyblue",
            "lightslategray",
            "lightslategrey",
            "lightsteelblue",
            "lightyellow",
            "lime",
            "limegreen",
            "linen",
            "magenta",
            "maroon",
            "mediumaquamarine",
            "mediumblue",
            "mediumorchid",
            "mediumpurple",
            "mediumseagreen",
            "mediumslateblue",
            "mediumspringgreen",
            "mediumturquoise",
            "mediumvioletred",
            "midnightblue",
            "mintcream",
            "mistyrose",
            "moccasin",
            "navajowhite",
            "navy",
            "oldlace",
            "olive",
            "olivedrab",
            "orange",
            "orangered",
            "orchid",
            "palegoldenrod",
            "palegreen",
            "paleturquoise",
            "palevioletred",
            "papayawhip",
            "peachpuff",
            "peru",
            "pink",
            "plum",
            "powderblue",
            "purple",
            "red",
            "rosybrown",
            "royalblue",
            "saddlebrown",
            "salmon",
            "sandybrown",
            "seagreen",
            "seashell",
            "sienna",
            "silver",
            "skyblue",
            "slateblue",
            "slategray",
            "slategrey",
            "snow",
            "springgreen",
            "steelblue",
            "tan",
            "teal",
            "thistle",
            "tomato",
            "turquoise",
            "violet",
            "wheat",
            "white",
            "whitesmoke",
            "yellow",
            "yellowgreen",
        ]
        for n in SVG_NAMES:
            with self.subTest(n):
                color = RGBAColor.from_css(n)
                n2 = color.to_svg_name_or_hex()
                self.assertNotRegex(n2, "^#[0-9A-F]+$", f"Named SVG color does not roundtrip: {n}")  # type: ignore
                color2 = RGBAColor.from_css(n2)
                self.assertEqual(color2, color)
        with self.assertRaises(ValueError):
            RGBAColor.from_css("currentcolor")

    def test_x11_names(self):
        X11_NAMES = [
            "grey100",
            "dark grey",
            "DarkGrey",
            "dark gray",
            "DarkGray",
            "dark blue",
            "DarkBlue",
            "dark cyan",
            "DarkCyan",
            "dark magenta",
            "DarkMagenta",
            "dark red",
            "Darkred",
            "Light Green",
            "Lightgreen",
            "Crimson",
            "Indigo",
            "Olive",
            "Rebecca Purple",
            "Rebeccapurple",
            "Silver",
            "Teal",
        ]
        for n in X11_NAMES:
            with self.subTest(n) as st:
                color = RGBAColor.from_x11_name(n)
                n2 = color.to_x11_name()
                self.assertIsNotNone(
                    n2, f"Named X11 color does not partially roundtrip: {n}"
                )
                color2 = RGBAColor.from_x11_name(n2)  # type: ignore
                self.assertEqual(color2, color)

    def test_qt(self):
        cases = {
            "transparent": "#00000000",
            "red": "#ff0000",
            "#abc": "#aabbcc",
            "#123abc": "#123abc",
            "#1d3a5b7c": "#3a5b7c1d",  # #aarrggbb: #rrggbbaa
            "#ab1cd2ef3": "#abcdef",
            "#1234abcd5678": "#12ab56",
        }
        for q, c in cases.items():
            qt = RGBAColor.from_qt(q)
            css = RGBAColor.from_css(c)
            self.assertEqual(qt, css)
            roundtrip = qt.to_qt()
            if len(q) != 9:
                self.assertEqual(roundtrip, c)
            self.assertEqual(RGBAColor.from_qt(roundtrip), css)

    def test_random(self):
        rand = random.Random(42)
        for _ in range(65536):
            x = rand.getrandbits(32)
            h = f"#{x:08X}"
            color = RGBAColor(x)
            color2 = RGBAColor.parse(h)
            self.assertEqual(color2, color)
            self.assertEqual(int(color), x)
            self.assertEqual(color.to_hex_rrggbbaa(), h.casefold())

    def test_fractions(self):
        test_sequence = (
            Fraction(0),
            Fraction(64, 255),
            Fraction(128, 255),
            Fraction(192, 255),
            Fraction(1),
        )
        for r in test_sequence:
            for g in test_sequence:
                for b in test_sequence:
                    for a in test_sequence:
                        s = f"{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}{int(a*255):02X}"
                        color = RGBAColor(int(s, base=16))
                        color2 = RGBAColor.parse("#" + s)
                        self.assertEqual(color2, color)
                        color3 = RGBAColor(
                            red=int(r * 255),
                            green=int(g * 255),
                            blue=int(b * 255),
                            alpha=int(a * 255),
                        )
                        self.assertEqual(color3, color)
                        color4 = RGBAColor.from_fractions(r, g, b, a)
                        self.assertEqual(color4, color)
                        f = color.to_fractions()
                        self.assertTupleEqual(f, (r, g, b, a))
                        p = color.to_premultiplied()
                        self.assertTupleEqual(p, (r * a, g * a, b * a, a))
                        o = color.opacify()
                        self.assertEqual(o.alpha, RGBAColor.MAX_CHANNEL_VALUE)
        
    def test_interpolation(self):
        # NOTE: For other interpolation methods, use the visual test.
        color1 = RGBAColor("#ABCDEF00")
        color2 = RGBAColor("#808080FF")
        interpolated = color1.interpolate(0.25, color2, interpolation=ColorSystem.SRGB)
        self.assertEqual(interpolated, RGBAColor("#80808040"))
        # XXX: There is no guarantee in the CSS algorithm that the result of 
        # interpolation with proportion 0 or 1 be equal to either endpoint.