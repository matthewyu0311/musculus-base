from collections import deque
from collections.abc import Callable, Iterable, Sequence
from enum import Enum, StrEnum
from functools import lru_cache
from math import (
    atan2,
    cbrt,
    copysign,
    cos,
    degrees,
    exp,
    fma,
    isnan,
    nan,
    radians,
    sin,
    sqrt,
    tau,
)
from typing import Any, Literal, cast

from .linalg import (
    Matrix_3x3,
    MATRIX_IDENTITY_3x3,
    Tuple3,
    Tuple4,
    matrix_inverse,
    matrix_linear_map_3x3,
    matrix_linear_map_3x3_fma,
    matrix_multiply,
    matrix_unary,
    vector_length,
    vector_scalar_mul,
    vector_sub,
)
from .number import (
    FracOrFloat,
    FracOrInt,
    clamp,
    frac,
    frac_float,
    frac_int,
)

try:
    import numpy as np
except ImportError:
    np = None


def matrix_precise(
    row0: tuple[FracOrFloat | str, FracOrFloat | str, FracOrFloat | str],
    row1: tuple[FracOrFloat | str, FracOrFloat | str, FracOrFloat | str],
    row2: tuple[FracOrFloat | str, FracOrFloat | str, FracOrFloat | str],
) -> Matrix_3x3:
    return cast(
        Matrix_3x3,
        (
            tuple(map(frac_int, row0)),
            tuple(map(frac_int, row1)),
            tuple(map(frac_int, row2)),
        ),
    )


def _output(v):
    if isinstance(v, Iterable):
        return tuple(map(frac_float, v))
    return (frac_float(v),)


matmap_fast = matrix_linear_map_3x3_fma
matmap_exact = matrix_linear_map_3x3
matmul_exact = matrix_multiply
matinv_exact = matrix_inverse

class ColorSystem(StrEnum):
 SRGB = "srgb"
 HSL = "hsl"
 HSV = "hsv"
 HWB = "hwb"
 CMYK = "cmyk"
 WAVELENGTH = "wavelength"
 SRGB_LINEAR = "srgb-linear"
 DISPLAY_P3 = "display-p3"
 DISPLAY_P3_LINEAR = "display-p3-linear"
 XYZ_D65 = "xyz-d65"
 XYZ = "xyz-d65"
 XYZ_D50 = "xyz-d50"
 A98_RGB = "a98-rgb"
 A98_RGB_LINEAR = "a98-rgb-linear"
 PROPHOTO_RGB = "prophoto-rgb"
 PROPHOTO_RGB_LINEAR = "prophoto-rgb-linear"
 REC2020 = "rec2020"
 REC2020_LINEAR = "rec2020-linear"
 LMS = "lms"
 LMS_CBRT = "lms-cbrt"
 LAB = "lab"
 LCH = "lch"
 OKLAB = "oklab"
 OKLCH = "oklch"

COLOR_SYSTEM_CONVERSIONS: dict[
    ColorSystem, dict[ColorSystem, Callable | Matrix_3x3 | None]
] = {}
FAST_CONVERSIONS: dict[ColorSystem, dict[ColorSystem, Matrix_3x3 | Any]] = {}


def _get_children(node, fast):
    children = set(COLOR_SYSTEM_CONVERSIONS[node].keys())
    if not fast:
        return children
    try:
        children.update(FAST_CONVERSIONS[node].keys())
    except KeyError:
        pass
    return children


@lru_cache
def convert_graph(
    from_system: ColorSystem, to_system: ColorSystem, *, fast: bool = True
) -> Sequence[ColorSystem]:

    # BFS Graph traversal algorithmn
    q: deque[ColorSystem] = deque()
    q.append(from_system)
    visited = {from_system}
    nodes = {}
    while q:
        node = q.popleft()
        try:
            children = _get_children(node, fast)
        except KeyError:
            break
        for next_node in children:
            if next_node not in visited:
                q.append(next_node)
                visited.add(next_node)
                nodes[next_node] = node
    path = deque()
    node = to_system
    while node is not None:
        path.append(node)
        try:
            node = nodes[node]
        except KeyError:
            break
    if path[-1] == from_system:
        return tuple(reversed(path))
    return ()


_clear_cache_on_register = False


def register_conversion(
    from_system: ColorSystem,
    to_system: ColorSystem,
    forward: Callable | Matrix_3x3,
    inverse: Callable | Matrix_3x3 | None = None,
):
    if not isinstance(forward, Callable):
        try:
            inverse = matinv_exact(forward)
        except ValueError, ArithmeticError:
            pass
    try:
        d = COLOR_SYSTEM_CONVERSIONS[from_system]
    except KeyError:
        d = {}
        COLOR_SYSTEM_CONVERSIONS[from_system] = d
    d[to_system] = forward
    if inverse is not None:
        try:
            d = COLOR_SYSTEM_CONVERSIONS[to_system]
        except KeyError:
            d = {}
            COLOR_SYSTEM_CONVERSIONS[to_system] = d
        d[from_system] = inverse
    if _clear_cache_on_register:
        convert_graph.cache_clear()


def _rgb_to_hslsvwb(red, green, blue):
    """Convert RGB proportions into HSL, HSV and HWB (hue, whiteness, blackness) color parameters.

    :param red: Red channel value, between zero and one inclusive.
    :type red: :class:`Fraction`
    :param green: Green channel value, between zero and one inclusive.
    :type green: :class:`Fraction`
    :param blue: Blue channel value, between zero and one inclusive.
    :type blue: :class:`Fraction`
    :return: A 7-tuple of `(hue6, saturation_hsl, lightness, saturation_hsv, value, whiteness, blackness)`,
        all values between zero and one inclusive.
    """

    whiteness: FracOrInt = min(red, green, blue)
    value: FracOrInt = max(red, green, blue)
    blackness = 1 - value
    t1_plus_t2 = whiteness + value
    chroma = value - whiteness
    white_plus_black = whiteness + blackness
    if white_plus_black > 1:
        # Equivalent to if chroma < 0, which should never happen
        # Scale down white and black so that they sum to 1
        whiteness = frac(whiteness, white_plus_black)
        blackness = frac(whiteness, white_plus_black)
    lightness = frac(t1_plus_t2, 2)
    if chroma == 0:
        # Grey
        return 0, 0, lightness, 0, value, whiteness, blackness
    if red == value:
        hue6 = frac((green - blue), chroma) % 6
    elif green == value:
        hue6 = frac((blue - red), chroma) + 2
    else:
        hue6 = frac((red - green), chroma) + 4
    if lightness == 0 or lightness == 1:
        saturation_hsl = 0
    else:
        saturation_hsl = frac(chroma, (1 - abs(t1_plus_t2 - 1)))
    if value == 0:
        saturation_hsv = 0
    else:
        saturation_hsv = frac(chroma, value)
    return (
        hue6,
        saturation_hsl,
        lightness,
        saturation_hsv,
        value,
        whiteness,
        blackness,
    )


def _convert_impl(
    from_system: ColorSystem,
    to_system: ColorSystem,
    values: Iterable[FracOrFloat] | FracOrFloat,
    *,
    fast: bool = True,
) -> dict:
    if from_system == to_system:
        return {to_system: values}
    matmap = matmap_fast if fast else matrix_linear_map_3x3
    output = {}
    path = convert_graph(from_system, to_system, fast=fast)
    for s in path:
        to_system = s
        if to_system != from_system:
            if fast:
                try:
                    fn = FAST_CONVERSIONS[from_system][to_system]
                except KeyError:
                    fn = COLOR_SYSTEM_CONVERSIONS[from_system][to_system]
            else:
                fn = COLOR_SYSTEM_CONVERSIONS[from_system][to_system]
            if callable(fn):
                if isinstance(values, Iterable):
                    values = cast(Iterable[FracOrFloat], fn(values))
                else:
                    values = cast(Iterable[FracOrFloat], fn((values,)))
            elif isinstance(fn, Iterable):
                # fn is a matrix
                if isinstance(values, Iterable):
                    if np is not None and fast:
                        values = np.matmul(
                            fn, values, dtype=np.double, casting="unsafe"
                        )
                    else:
                        values = matmap(cast(Matrix_3x3, fn), cast(Tuple3, values))
                else:
                    raise TypeError(
                        "Cannot perform matrix multiplication with a scalar value"
                    )
            elif fn is None:
                pass
            else:
                raise TypeError("Conversion must be either a callable or a matrix")
        from_system = s
        if not isinstance(values, Iterable):
            values = (values,)
        output[to_system] = values
    return output


def convert(
    from_system: ColorSystem,
    to_system: ColorSystem,
    values: Iterable[FracOrFloat] | FracOrFloat,
    *,
    fast: bool = True,
) -> tuple[FracOrFloat, ...]:
    """The main function. Always returns a tuple of Python numbers,
    so it is safe to destructure the returned value."""
    if from_system == to_system:
        return _output(values)
    else:
        try:
            v = _convert_impl(from_system, to_system, values, fast=fast)[to_system]
            return _output(v)
        except KeyError:
            raise ValueError(f"Cannot convert from {from_system!r} to {to_system!r}")


def deltaE2000(reference_lab: Tuple3, sample_lab: Tuple3) -> float:
    """Adapted from https://drafts.csswg.org/css-color-4/#color-difference-2000"""
    Gfactor = 25**7
    L1, a1, b1 = reference_lab
    L2, a2, b2 = sample_lab
    C1 = sqrt(a1**2 + b1**2)
    C2 = sqrt(a2**2 + b2**2)
    Cbar = (C1 + C2) / 2
    C7 = Cbar**7
    G = 0.5 * (1 - sqrt(C7 / (C7 + Gfactor)))
    adash1 = (1 + G) * a1
    adash2 = (1 + G) * a2
    Cdash1 = sqrt(adash1**2 + b1**2)
    Cdash2 = sqrt(adash2**2 + b2**2)
    if adash1 == 0 and b1 == 0:
        h1 = h2 = 0
    else:
        h1 = atan2(b1, adash1)
        h2 = atan2(b2, adash2)
    if h1 < 0:
        h1 += tau
    if h2 < 0:
        h2 += tau
    h1 = degrees(h1)
    h2 = degrees(h2)
    delta_L = L2 - L1
    delta_C = Cdash2 - Cdash1
    hdiff = h2 - h1
    hsum = h1 + h2
    habs = abs(hdiff)
    if Cdash1 * Cdash2 == 0:
        delta_h = 0
    elif habs <= 180:
        delta_h = hdiff
    elif hdiff > 180:
        delta_h = hdiff - 360
    elif hdiff < -180:
        delta_h = hdiff + 360
    else:
        assert False
    delta_H = 2 * sqrt(Cdash2 * Cdash1) * sin(radians(delta_h / 2))
    Ldash = (L1 + L2) / 2
    Cdash = (Cdash1 + Cdash2) / 2
    Cdash7 = Cdash**7
    if Cdash1 == 0 and Cdash2 == 0:
        hdash = hsum
    elif habs <= 180:
        hdash = hsum / 2
    elif hsum < 360:
        hdash = (hsum + 360) / 2
    else:
        hdash = (hsum - 360) / 2
    lsq = (Ldash - 50) ** 2
    SL = 1 + ((0.015 * lsq) / sqrt(20 + lsq))
    SC = 1 + 0.045 * Cdash
    T = (
        1
        - (0.17 * cos(radians((hdash - 30))))
        + (0.24 * cos(radians(2 * hdash)))
        + (0.32 * cos(radians(((3 * hdash) + 6))))
        - (0.20 * cos(radians(((4 * hdash) - 63))))
    )
    SH = 1 + 0.015 * Cdash * T
    delta_θ = 30 * exp(-1 * (((hdash - 275) / 25) ** 2))
    RC = 2 * sqrt(Cdash7 / (Cdash7 + Gfactor))
    RT = -1 * sin(radians(2 * delta_θ)) * RC
    dE = (
        (delta_L / SL) ** 2
        + (delta_C / SC) ** 2
        + (delta_H / SH) ** 2
        + RT * (delta_C / SC) * (delta_H / SH)
    )
    return sqrt(dE)


def deltaEOK(
    reference_oklab: Tuple3, sample_oklab: Tuple3, *, fast: bool = True
) -> float:
    if fast and np is not None:
        sub = np.subtract(reference_oklab, sample_oklab, dtype=np.double, casting="unsafe")  # type: ignore
        return float(np.linalg.norm(sub))
    return vector_length(vector_sub(reference_oklab, sample_oklab))


def ps_greyscale(values: Tuple3) -> FracOrFloat:
    """The greyscale value, equal to `0.3 * red + 0.59 * green + 0.11 * blue`.
    Taken from `xcolor` LaTeX package documentation from PostScript specification.

    :return: Greyscale value between zero and one inclusive.
    """
    red, green, blue = values
    return frac((300 * red + 590 * green + 110 * blue), 1000)


def luminance_bt601(values: Tuple3) -> FracOrFloat:
    """The luminance value, equal to `0.299 * red + 0.587 * green + 0.114 * blue`.
    Taken from ITU-R Recommendation BT.601.

    :return: Luminance value between zero and one inclusive.
    """
    red, green, blue = values
    return frac((299 * red + 587 * green + 114 * blue), 1000)


def rgb_to_hsl(values):
    h6, sl, l, sv, v, w, b = _rgb_to_hslsvwb(*values)
    return h6 * 60, sl * 100, l * 100


def rgb_to_hsv(values):
    h6, sl, l, sv, v, w, b = _rgb_to_hslsvwb(*values)
    return h6 * 60, sv * 100, v * 100


def rgb_to_hwb(values):
    h6, sl, l, sv, v, w, b = _rgb_to_hslsvwb(*values)
    return h6 * 60, w * 100, b * 100


def hsl_to_rgb(values):
    hue, saturation_l, lightness = values
    h6 = hue / 60
    sl = saturation_l / 100
    l = lightness / 100
    if sl <= 0:
        # CSS Color 3 requiremeent
        return l, l, l
    if l * 2 <= 1:
        t2 = l * (sl + 1)
    else:
        t2 = l + sl - (l * sl)
    t1 = l * 2 - t2
    return _t1_t2_h6_to_rgb(t1, t2, h6)


def hsv_to_rgb(values):
    hue, saturation_v, value = values
    h6 = hue / 60
    sv = saturation_v / 100
    v = value / 100
    if v == 0:
        return 0, 0, 0
    if sv == 0:
        return v, v, v
    return _t1_t2_h6_to_rgb(v * (1 - sv), v, h6)


def hwb_to_rgb(values):
    hue, whiteness, blackness = values
    h6 = hue / 60
    w = whiteness / 100
    b = blackness / 100
    white_plus_black = w + b
    if white_plus_black > 1:
        w = frac(w, white_plus_black)
        b = frac(b, white_plus_black)
    return _t1_t2_h6_to_rgb(w, 1 - b, h6)


def _t1_t2_h6_to_rgb(t1, t2, h6):
    # t1 = white, t2 = value
    chroma = t2 - t1
    if chroma == 0:
        return t1, t1, t1
    output = []
    for delta in (2, 0, -2):
        x = (h6 + delta) % 6
        if x < 1:
            output.append(chroma * x + t1)
        elif x < 3:
            output.append(t2)
        elif x <= 4:
            output.append(chroma * (4 - x) + t1)
        else:
            output.append(t1)
    return output


def rgb_to_cmyk_naive(srgb: Tuple3) -> Tuple4:
    """Implements naive conversion from sRGB to uncalibrated CMYK."""
    red, green, blue = srgb
    black = 1 - max(red, green, blue)
    if black == 1:
        cyan = magenta = yellow = 0
    else:
        cyan = (1 - red - black) / (1 - black)
        magenta = (1 - green - black) / (1 - black)
        yellow = (1 - blue - black) / (1 - black)
    return cyan, magenta, yellow, black


def cmyk_naive_to_rgb(cmyk: Tuple4) -> Tuple3:
    """Implements naive conversion from uncalibrated CMYK to sRGB."""
    cyan, magenta, yellow, black = cmyk
    red = 1 - min(1, cyan * (1 - black) + black)
    green = 1 - min(1, magenta * (1 - black) + black)
    blue = 1 - min(1, yellow * (1 - black) + black)
    return red, green, blue


def wavelength_to_rgb(wavelength: FracOrFloat, *, gamma: float = 0.8) -> Tuple3:
    """Convert wavelength to an approximate RGB value.
    Wavelengths outside 380 to 780 nm will result in blackness.
    This is a rough approximation:
    * Within the linear region of increasing wavelength (440 to 700 nm),
      the colors have monotonically decreasing hue, saturations = 1, lightness = 0.5, value = 1
    * No guarantee is made on roundtripping from wavelength to color or vice versa.

    :param wavelength: Wavelength in nanometers.
    :type wavelength: float
    :param gamma: Gamma value (positive), defaults to 0.8
    :type gamma: float | Fraction, optional
    :return: A 3-tuple of `(red, green, blue)`, all values are floats between zero and one inclusive.
    """
    # Accept and return float because our process is in general inexact (due to gamma)
    if not gamma > 0:
        raise ValueError("Gamma value must be positive")
    if 380 <= wavelength <= 440:
        s = (3 + 7 * (wavelength - 380) / (420 - 380)) / 10
        r = s * (440 - wavelength) / (440 - 380)
        g = 0
        b = s
    # elif 420 <= wavelength <= 440:
    #     r = (440 - wavelength) / (440 - 380)
    #     g = 0
    #     b = 1
    elif 440 <= wavelength <= 490:
        r = 0
        g = (wavelength - 440) / (490 - 440)
        b = 1
    elif 490 <= wavelength <= 510:
        r = 0
        g = 1
        b = (510 - wavelength) / (510 - 490)
    elif 510 <= wavelength <= 580:
        r = (wavelength - 510) / (580 - 510)
        g = 1
        b = 0
    elif 580 <= wavelength <= 645:
        r = 1
        g = (645 - wavelength) / (645 - 580)
        b = 0
    elif 645 <= wavelength <= 700:
        r = 1
        g = 0
        b = 0
    elif 700 <= wavelength <= 780:
        r = (3 + 7 * (780 - wavelength) / (780 - 700)) / 10
        g = 0
        b = 0
    else:
        r = 0
        g = 0
        b = 0
    return (
        clamp(r**gamma, 0.0, 1.0),
        clamp(g**gamma, 0.0, 1.0),
        clamp(b**gamma, 0.0, 1.0),
    )


def rgb_to_wavelength(values: Tuple3, *, gamma: float = 0.8) -> float:
    """Convert RGB values to an approximate wavelength value.
    This is a rough approximation:
    * For input colors of increasing hue, the wavelength will monotonically decrease
      if the wavelength is within the linear region (440 to 700 nm).
    * Red colors (640 to 700 nm) and "infra-red" colors (>700 nm) may be mapped to 700 nm.
    * Non-saturated colors will be mapped to a color of the same hue.
    * No guarantee is made on roundtripping from wavelength to color or vice versa.

    :param red: Red channel value, between zero and one inclusive.
    :type red: float | :class:`Fraction`
    :param green: Green channel value, between zero and one inclusive.
    :type green: float |  :class:`Fraction`
    :param blue: Blue channel value, between zero and one inclusive.
    :type blue: float | :class:`Fraction`
    :param gamma: Gamma value (positive), defaults to 0.8
    :type gamma: float | Fraction, optional
    :return: A rough approximation of the corresponding wavelength in nanometers,
        or `nan` if the color has no saturation.
    """
    # Accept and return float because our process is in general inexact (due to gamma)
    red, green, blue = values
    if not gamma > 0:
        raise ValueError(f"Gamma <= 0: {gamma}")
    if red == green == blue:
        return nan
    hue, *_ = _rgb_to_hslsvwb(frac(red), frac(green), frac(blue))
    red, green, blue = hwb_to_rgb((hue, 0, 0))
    inv_gamma = 1 / gamma
    r = float(red**inv_gamma)
    g = float(green**inv_gamma)
    b = float(blue**inv_gamma)
    if r > g == b:
        # 645..700, 700..780
        if r == 1:
            return 700.0
        return 780 - (780 - 700) * (r * 10 - 3) / 7
    if r > g > b:
        # 580..645
        g /= r
        return 645 - g * (645 - 580)
    elif r == g > b:
        return 580.0
    elif g > r > b:
        # 510..580
        r /= g
        return 510 + r * (580 - 510)
    elif g > r == b:
        return 510.0
    elif g > b > r:
        # 490..510
        b /= g
        return 510 - b * (510 - 490)
    elif g == b > r:
        return 490.0
    elif b > g > r:
        # 440..490
        g /= b
        return 440 + g * (490 - 440)
    else:
        # 380..440
        # s = 0.3 + 0.7 * (wavelength - 380) / (420 - 380)
        # r = s * (440 - wavelength) / (440 - 380)
        # b = s
        # r / b = (440 - wavelength) / (440 - 380)
        r /= b
        return 440 - r * (440 - 380)


def srgb_transfer_lin(values):
    return tuple(
        (
            srgb
            if srgb in {-1, 0, 1}
            else (
                srgb / 12.92
                if abs(srgb) <= 0.04045
                else copysign(((abs(srgb) + 0.055) / 1.055) ** 2.4, srgb)
            )
        )
        for srgb in values
    )


def srgb_transfer_gam(values):
    return tuple(
        (
            linear
            if linear in {-1, 0, 1}
            else (
                linear * 12.92
                if abs(linear) <= 0.0031308
                else copysign(fma(1.055, abs(linear) ** (1.0 / 2.4), -0.055), linear)
            )
        )
        for linear in values
    )


# http://www.brucelindbloom.com/index.html?Eqn_ChromAdapt.html
ILLUMINANTS_XYZ = {
    "D50": (0.3457 / 0.3585, 1.0, (1.0 - 0.3457 - 0.3585) / 0.3585),
    "D65": (0.3127 / 0.3290, 1.0, (1.0 - 0.3127 - 0.3290) / 0.3290),
    "A": (1.09850, 1.00000, 0.35585),
    "B": (0.99072, 1.00000, 0.85223),
    "C": (0.98074, 1.00000, 1.18232),
    # "D50":(0.96422, 1.00000, 0.82521),
    "D55": (0.95682, 1.00000, 0.92149),
    # "D65":(0.95047, 1.00000, 1.08883),
    "D75": (0.94972, 1.00000, 1.22638),
    "E": (1.00000, 1.00000, 1.00000),
    "F2": (0.99186, 1.00000, 0.67393),
    "F7": (0.95041, 1.00000, 1.08747),
    "F11": (1.00962, 1.00000, 0.64350),
}

# The srgb-linear to xyz-d65 conversions is exact
LINEAR_TO_XYZ_D65_MATRIX = matrix_precise(
    (frac(506752, 1228815), frac(87881, 245763), frac(12673, 70218)),
    (frac(87098, 409605), frac(175762, 245763), frac(12673, 175545)),
    (frac(7918, 409605), frac(87881, 737289), frac(1001167, 1053270)),
)

# LMS and OKLab From https://bottosson.github.io/posts/oklab/
OKLAB_TO_LMS_CBRT_MATRIX = matrix_precise(
    (1, "0.3963377773761749", "0.2158037573099136"),
    (1, "-0.1055613458156586", "-0.0638541728258133"),
    (1, "-0.0894841775298119", "-1.2914855480194092"),
)

XYZ_D65_TO_LMS_MATRIX = matrix_precise(
    ("0.8190224379967030", "0.3619062600528904", "-0.1288737815209879"),
    ("0.0329836539323885", "0.9292868615863434", "0.0361446663506424"),
    ("0.0481771893596242", "0.2642395317527308", "0.6335478284694309"),
)

DISPLAY_P3_LINEAR_TO_XYZ_D65_MATRIX = matrix_precise(
    (frac(608311, 1250200), frac(189793, 714400), frac(198249, 1000160)),
    (frac(35783, 156275), frac(247089, 357200), frac(198249, 2500400)),
    (frac(0, 1), frac(32229, 714400), frac(5220557, 5000800)),
)

XYZ_D50_TO_PROPHOTO_RGB_LINEAR_MATRIX = matrix_precise(
    ("1.34578688164715830", "-0.25557208737979464", "-0.05110186497554526"),
    ("-0.54463070512490190", "1.50824774284514680", "0.02052744743642139"),
    (0, 0, "1.21196754563894520"),
)

A98_LINEAR_TO_XYZ_D65_MATRIX = matrix_precise(
    (frac(573536, 994567), frac(263643, 1420810), frac(187206, 994567)),
    (frac(591459, 1989134), frac(6239551, 9945670), frac(374412, 4972835)),
    (frac(53769, 1989134), frac(351524, 4972835), frac(4929758, 4972835)),
)

XYZ_D65_TO_REC2020_LINEAR_MATRIX = matrix_precise(
    (frac(30757411, 17917100), frac(-6372589, 17917100), frac(-4539589, 17917100)),
    (frac(-19765991, 29648200), frac(47925759, 29648200), frac(467509, 29648200)),
    (frac(792561, 44930125), frac(-1921689, 44930125), frac(42328811, 44930125)),
)

# Chromatic adaptations between XYZ spaces
# From http://www.brucelindbloom.com/index.html?Eqn_ChromAdapt.html

BRADFORD_MATRIX = matrix_precise(
    ("0.8951", "0.2664", "-0.1614"),
    ("-0.7502", "1.7135", "0.0367"),
    ("0.0389", "-0.0685", "1.0296"),
)
VON_KREIS_MATRIX = matrix_precise(
    ("0.4002", "0.7076", "-0.08081"),
    ("-0.2263", "1.16532", "0.0457"),
    (0, 0, "0.91822"),
)

type ChromaticAdaptation = Literal["xyz_scaling", "bradford", "von_kreis"]

CHROMATIC_ADAPTATION_METHODS = {
    "xyz_scaling": (MATRIX_IDENTITY_3x3, MATRIX_IDENTITY_3x3),
    "bradford": (BRADFORD_MATRIX, matinv_exact(BRADFORD_MATRIX)),
    "von_kreis": (VON_KREIS_MATRIX, matinv_exact(VON_KREIS_MATRIX)),
}


def chromatic_adaptation_matrix(
    Xw1: FracOrFloat,
    Yw1: FracOrFloat,
    Zw1: FracOrFloat,
    Xw2: FracOrFloat,
    Yw2: FracOrFloat,
    Zw2: FracOrFloat,
    *,
    method: ChromaticAdaptation = "bradford",
) -> Matrix_3x3:
    """This function returns a fraction matrix.
    While it is possible to use the resultant matrix directly,
    it is intended to be multiplied with other matrices."""

    # Precision, not performance, is key for this matrix
    ma, ma_inv = CHROMATIC_ADAPTATION_METHODS[method]
    rho_1, gamma_1, beta_1 = matmap_exact(ma, (Xw1, Yw1, Zw1))
    rho_2, gamma_2, beta_2 = matmap_exact(ma, (Xw2, Yw2, Zw2))
    matrix = (
        (frac(rho_2, rho_1), 0, 0),
        (0, frac(gamma_2, gamma_1), 0),
        (0, 0, frac(beta_2, beta_1)),
    )
    intermediate = matmul_exact(matrix, ma)
    result = matmul_exact(ma_inv, intermediate, mutable=False)
    return cast(Matrix_3x3, result)


XYZ_D50_TO_D65_BRADFORD_MATRIX = chromatic_adaptation_matrix(
    *ILLUMINANTS_XYZ["D50"], *ILLUMINANTS_XYZ["D65"], method="bradford"
)


def chromatic_adaptation(
    illuminant1: str,
    illuminant2: str,
    xyz_values: Tuple3,
    *,
    method: ChromaticAdaptation = "bradford",
    fast: bool = True,
):
    matrix: Any
    if illuminant1 == "D50" and illuminant2 == "D65" and method == "bradford":
        matrix = XYZ_D50_TO_D65_BRADFORD_MATRIX
    else:
        matrix = chromatic_adaptation_matrix(
            *ILLUMINANTS_XYZ[illuminant1], *ILLUMINANTS_XYZ[illuminant2], method=method
        )
    if np is not None and fast:
        return _output(
            np.matmul(matrix, cast(Any, xyz_values), dtype=np.double, casting="unsafe")
        )

    else:
        matmap = matmap_fast if fast else matrix_linear_map_3x3
        return _output(matmap(matrix, xyz_values))


# XYZ, Lab
_sigma = frac(6, 29)
_sigma_cube = _sigma * _sigma * _sigma
_frac_4_29 = frac(4, 29)


def _xyz_lab_f(v: FracOrFloat) -> FracOrFloat:
    if v > _sigma_cube:
        return cbrt(v)
    else:
        return v / _sigma / _sigma / 3 + _frac_4_29


def _xyz_lab_f_inv(v: FracOrFloat) -> FracOrFloat:
    if v > _sigma:
        return v**3
    else:
        return 3 * _sigma * _sigma * (v - _frac_4_29)


# The use of XYZ D50 is from https://drafts.csswg.org/css-color-4/#color-conversion-code
def xyz_d50_to_lab(values: Tuple3) -> Tuple3:
    x, y, z = values
    Xw_D50, Yw_D50, Zw_D50 = ILLUMINANTS_XYZ["D50"]
    fx = _xyz_lab_f(x / Xw_D50)
    fy = _xyz_lab_f(y / Yw_D50)
    fz = _xyz_lab_f(z / Zw_D50)

    return (
        116 * fy - 16,
        500 * (fx - fy),
        200 * (fy - fz),
    )


def lab_to_xyz_d50(values: Tuple3) -> Tuple3:
    L, a, b = values
    Xw_D50, Yw_D50, Zw_D50 = ILLUMINANTS_XYZ["D50"]
    fy = (L + 16) / 116
    fx = (a / 500) + fy
    fz = fy - (b / 200)

    x = _xyz_lab_f_inv(fx)
    if L > 8.0:
        y = fy * fy * fy
    else:
        y = L * 27 / 24389
    z = _xyz_lab_f_inv(fz)
    return x * Xw_D50, y * Yw_D50, z * Zw_D50


def lms_to_lms_cbrt(values):
    if np is not None:
        return np.cbrt(values, dtype=np.double, casting="unsafe")
    return map(cbrt, values)


def lms_cbrt_to_lms(values):
    if np is not None:
        return np.power(values, 3, dtype=np.double, casting="unsafe")
    return (i**3 for i in values)


def lab_to_lch(values: Tuple3) -> Tuple3:
    L, a, b = values
    C = sqrt(a * a + b * b)
    h = degrees(atan2(b, a))
    return L, C, h


def lch_to_lab(values: Tuple3) -> Tuple3:
    L, C, h = values
    if C == 0 or isnan(h):
        a = b = 0
    else:
        hr = radians(h)
        a = C * cos(hr)
        b = C * sin(hr)
    return L, a, b


###################### Exponential transfer functions


def _exp_fn(exponent):
    return lambda values: tuple(copysign(abs(v) ** exponent, v) for v in values)


def _exp_fn_thres(exponent, threshold, coeff):
    return lambda values: tuple(
        (v * coeff if abs(v) <= threshold else copysign(abs(v) ** exponent, v))
        for v in values
    )


prophoto_rgb_gam = _exp_fn_thres(1 / 1.8, 1 / 512, 16)
prophoto_rgb_lin = _exp_fn_thres(1.8, 16 / 512, 1 / 16)
a98_transfer_lin = _exp_fn(563 / 256)
a98_transfer_gam = _exp_fn(256 / 563)
rec2020_transfer_lin = _exp_fn(2.4)
rec2020_transfer_gam = _exp_fn(1 / 2.4)


def build_linear_matrices(
    center: ColorSystem = ColorSystem.XYZ_D65,
    *,
    exclude=(),
    max_level: int | None = None,
):
    """Build direct matrices from and to the central node."""
    visited = set(exclude)
    linear_systems = deque()
    changes = {}

    center_dict = COLOR_SYSTEM_CONVERSIONS[center]

    def recur(level, node, center_to_node_matrix, node_to_center_matrix):
        visited.add(node)
        linear_systems.append(node)
        for branch, node_to_branch_matrix in COLOR_SYSTEM_CONVERSIONS[node].items():
            if branch in visited:
                continue
            if not isinstance(node_to_branch_matrix, Iterable):
                continue
            try:
                branch_dict = COLOR_SYSTEM_CONVERSIONS[branch]
                branch_to_node_matrix = branch_dict[node]
            except KeyError:
                continue
            if not isinstance(branch_to_node_matrix, Iterable):
                continue
            if node == center:
                center_to_branch_matrix = node_to_branch_matrix
                branch_to_center_matrix = branch_to_node_matrix
            else:
                try:
                    center_to_branch_matrix = cast(Matrix_3x3, center_dict[branch])
                    if not isinstance(center_to_branch_matrix[0][0], FracOrInt):
                        raise TypeError
                except (KeyError, TypeError) as e:
                    center_to_branch_matrix = matmul_exact(
                        cast(Matrix_3x3, node_to_branch_matrix), center_to_node_matrix
                    )
                    if isinstance(e, KeyError):
                        changes.setdefault(center, {}).setdefault(
                            branch, center_to_branch_matrix
                        )
                try:
                    branch_to_center_matrix = cast(Matrix_3x3, branch_dict[center])
                    if not isinstance(branch_to_center_matrix[0][0], FracOrInt):
                        raise TypeError
                except (KeyError, TypeError) as e:
                    branch_to_center_matrix = matmul_exact(
                        node_to_center_matrix, cast(Matrix_3x3, branch_to_node_matrix)
                    )
                    if isinstance(e, KeyError):
                        changes.setdefault(branch, {}).setdefault(
                            center, branch_to_center_matrix
                        )
            if max_level is None or max_level < 0 or level < max_level:
                recur(
                    level + 1, branch, center_to_branch_matrix, branch_to_center_matrix
                )

    recur(0, center, MATRIX_IDENTITY_3x3, MATRIX_IDENTITY_3x3)
    for f, change in changes.items():
        from_dict = FAST_CONVERSIONS.setdefault(f, {})
        for t, mat in change.items():
            if np is not None:
                mat = np.array(mat, dtype=np.double)
            else:
                mat = cast(Matrix_3x3, matrix_unary(float, mat))
            from_dict[t] = mat
    if _clear_cache_on_register:
        convert_graph.cache_clear()
    return list(linear_systems)


def register_scalar(from_system, to_scalar, forward, inverse):
    system_to_scalar = lambda v: (forward(v),)
    scalar_to_system = lambda v: inverse(*v) if isinstance(v, Iterable) else inverse(v)
    register_conversion(
        from_system,
        to_scalar,
        system_to_scalar,
        scalar_to_system,
    )


# Linear transformations
register_conversion(ColorSystem.XYZ_D50, ColorSystem.XYZ_D65, XYZ_D50_TO_D65_BRADFORD_MATRIX)
register_conversion(ColorSystem.SRGB_LINEAR, ColorSystem.XYZ_D65, LINEAR_TO_XYZ_D65_MATRIX)
register_conversion(ColorSystem.DISPLAY_P3_LINEAR, ColorSystem.XYZ_D65, DISPLAY_P3_LINEAR_TO_XYZ_D65_MATRIX)
register_conversion(
    ColorSystem.XYZ_D50, ColorSystem.PROPHOTO_RGB_LINEAR, XYZ_D50_TO_PROPHOTO_RGB_LINEAR_MATRIX
)
register_conversion(ColorSystem.A98_RGB_LINEAR, ColorSystem.XYZ_D65, A98_LINEAR_TO_XYZ_D65_MATRIX)
register_conversion(ColorSystem.XYZ_D65, ColorSystem.REC2020_LINEAR, XYZ_D65_TO_REC2020_LINEAR_MATRIX)
register_conversion(ColorSystem.OKLAB, ColorSystem.LMS_CBRT, OKLAB_TO_LMS_CBRT_MATRIX)
register_conversion(ColorSystem.XYZ_D65, ColorSystem.LMS, XYZ_D65_TO_LMS_MATRIX)

build_linear_matrices(ColorSystem.XYZ_D65)
build_linear_matrices(ColorSystem.LMS)  # Needed for OKLAB
build_linear_matrices(ColorSystem.SRGB_LINEAR)

# Non_LINEAR transformations
register_conversion(ColorSystem.SRGB, ColorSystem.HSL, rgb_to_hsl, hsl_to_rgb)
register_conversion(ColorSystem.SRGB, ColorSystem.HSV, rgb_to_hsv, hsv_to_rgb)
register_conversion(ColorSystem.SRGB, ColorSystem.HWB, rgb_to_hwb, hwb_to_rgb)
register_conversion(ColorSystem.SRGB, ColorSystem.CMYK, rgb_to_cmyk_naive, cmyk_naive_to_rgb)
register_conversion(ColorSystem.SRGB_LINEAR, ColorSystem.SRGB, srgb_transfer_gam, srgb_transfer_lin)
register_conversion(
    ColorSystem.DISPLAY_P3_LINEAR, ColorSystem.DISPLAY_P3, srgb_transfer_gam, srgb_transfer_lin
)
register_conversion(
    ColorSystem.PROPHOTO_RGB_LINEAR, ColorSystem.PROPHOTO_RGB, prophoto_rgb_gam, prophoto_rgb_lin
)
register_conversion(
    ColorSystem.REC2020_LINEAR, ColorSystem.REC2020, rec2020_transfer_gam, rec2020_transfer_lin
)
register_conversion(ColorSystem.A98_RGB_LINEAR, ColorSystem.A98_RGB, a98_transfer_gam, a98_transfer_lin)
register_conversion(ColorSystem.XYZ_D50, ColorSystem.LAB, xyz_d50_to_lab, lab_to_xyz_d50)
register_conversion(ColorSystem.LAB, ColorSystem.LCH, lab_to_lch, lch_to_lab)
register_conversion(ColorSystem.OKLAB, ColorSystem.OKLCH, lab_to_lch, lch_to_lab)
register_conversion(ColorSystem.LMS, ColorSystem.LMS_CBRT, lms_to_lms_cbrt, lms_cbrt_to_lms)

# Scalars
register_scalar("srgb", "wavelength", rgb_to_wavelength, wavelength_to_rgb)

_clear_cache_on_register = True

COLOR_SYSTEMS_UNLIMITED_GAMUT = {
    "xyz-d65",
    "xyz-d50",
    "lab",
    "lch",
    "oklab",
    "oklch",
    "lms",
}


def _delta(system1, color1, system2, color2):
    return deltaEOK(convert(system1, "oklab", color1), convert(system2, "oklab", color2))  # type: ignore


def _clip(values):
    if np is not None:
        return np.clip(values, 0, 1, dtype=np.double, casting="unsafe")
    return tuple(map(clamp, values))


def _in_gamut(values):
    return all(0 <= v <= 1 for v in values)


def _css_gamut_map_impl(
    origin_system: ColorSystem,
    values: Sequence[FracOrFloat],
    *,
    jnd: FracOrFloat = 0.02,
    epsilon: FracOrFloat = 0.0001,
    max_l: FracOrFloat = 1,
    min_l: FracOrFloat = 0,
) -> Iterable[FracOrFloat]:
    if origin_system in COLOR_SYSTEMS_UNLIMITED_GAMUT:
        return values
    if _in_gamut(values):
        return values
    graph = convert_graph(origin_system, "xyz-d65", fast=True)
    if not graph:
        raise ValueError(
            f"Cannot find a path from {origin_system} to OKLCh for gamut mapping."
        )
    elif graph[1] == f"{origin_system}-linear":
        candidate_system = graph[1]
    elif "srgb" in graph:
        candidate_system = ColorSystem.SRGB_LINEAR
    else:
        candidate_system = origin_system
    if origin_system in COLOR_SYSTEMS_UNLIMITED_GAMUT:
        return values

    candidate_values = _convert_impl(origin_system, candidate_system, values)[
        candidate_system
    ]
    origin_lch = _convert_impl(candidate_system, ColorSystem.OKLCH, candidate_values)["oklch"]
    l, chroma, hue = origin_lch
    if l >= max_l:
        # White
        return _convert_impl(ColorSystem.SRGB_LINEAR, origin_system, (1, 1, 1))[origin_system]
    elif l <= min_l:
        # Black
        return _convert_impl(ColorSystem.SRGB_LINEAR, origin_system, (0, 0, 0))[origin_system]

    clipped_candidate = _clip(candidate_values)
    E = _delta(candidate_system, candidate_values, candidate_system, clipped_candidate)
    if E < jnd:
        return _convert_impl(candidate_system, origin_system, clipped_candidate)[
            origin_system
        ]
    minimum = 0
    maximum = chroma
    min_in_gamut = True
    while (maximum - minimum) > epsilon:
        chroma = (minimum + maximum) / 2
        current_candidate = convert(ColorSystem.OKLCH, candidate_system, (l, chroma, hue))
        if min_in_gamut and _in_gamut(current_candidate):
            minimum = chroma
            continue
        else:
            clipped_candidate = _clip(current_candidate)
            E = _delta(
                candidate_system, clipped_candidate, candidate_system, current_candidate
            )
            if E < jnd:
                if jnd - E < epsilon:
                    return convert(candidate_system, origin_system, clipped_candidate)
                else:
                    min_in_gamut = False
                    minimum = chroma
            else:
                maximum = chroma
    return _convert_impl(candidate_system, origin_system, clipped_candidate)[
        origin_system
    ]


def css_gamut_map(
    origin_system: ColorSystem,
    values: Sequence[FracOrFloat],
    *,
    jnd: FracOrFloat = 0.02,
    epsilon: FracOrFloat = 0.0001,
    max_l: FracOrFloat = 1,
    min_l: FracOrFloat = 0,
) -> tuple[FracOrFloat, ...]:
    return _output(
        _css_gamut_map_impl(
            origin_system, values, jnd=jnd, epsilon=epsilon, max_l=max_l, min_l=min_l
        )
    )


def convert_into_gamut(
    from_system: ColorSystem,
    to_system: ColorSystem,
    values: Iterable[FracOrFloat] | FracOrFloat,
    *,
    jnd: FracOrFloat = 0.02,
    epsilon: FracOrFloat = 0.0001,
    max_l: FracOrFloat = 1,
    min_l: FracOrFloat = 0,
) -> tuple[FracOrFloat, ...]:
    color = _convert_impl(from_system, to_system, values)[to_system]
    return _output(
        _css_gamut_map_impl(
            to_system, color, jnd=jnd, epsilon=epsilon, max_l=max_l, min_l=min_l
        )
    )


# Interpolation between two <color> values takes place by executing the following steps:

# - checking the two colors for analogous components which will be carried forward
# - converting them to a given color space which will be referred to as the interpolation color space below.
#   If one or both colors are already in the interpolation color space, this conversion changes any powerless components to missing values
# - (if required) re-inserting carried forward values in the converted colors
# - (if required) fixing up the hues, depending on the selected <hue-interpolation-method>
# - changing the color components to premultiplied form
# - linearly interpolating each component of the computed value of the color separately
# - undoing premultiplication


class ComponentSpec(Enum):
    REDS = 0
    GREENS = 1
    BLUES = 2
    LIGHTNESS = 3
    COLORFULNESS = 4
    HUE = 5
    OPPONENT_A = 6
    OPPONENT_B = 7

    # HWB
    WHITENESS = 8
    BLACKNESS = 9


RGB_SPEC = {
    "r": ComponentSpec.REDS,
    "g": ComponentSpec.GREENS,
    "b": ComponentSpec.BLUES,
}
XYZ_SPEC = {
    "x": ComponentSpec.REDS,
    "y": ComponentSpec.GREENS,
    "z": ComponentSpec.BLUES,
}
HSL_SPEC = {
    "H": ComponentSpec.HUE,
    "S": ComponentSpec.COLORFULNESS,
    "L": ComponentSpec.LIGHTNESS,
}
HWB_SPEC = {
    "H": ComponentSpec.HUE,
    "W": ComponentSpec.WHITENESS,
    "B": ComponentSpec.BLACKNESS,
}
LAB_SPEC = {
    "L": ComponentSpec.LIGHTNESS,
    "a": ComponentSpec.OPPONENT_A,
    "b": ComponentSpec.OPPONENT_B,
}
LCH_SPEC = {
    "L": ComponentSpec.LIGHTNESS,
    "C": ComponentSpec.COLORFULNESS,
    "h": ComponentSpec.HUE,
}

# Only color systems that support interpolation (i.e. defined by CSS Color 4) will have a component spec.
COMPONENTS_SPEC: dict[ColorSystem, dict[str, ComponentSpec]] = {
    ColorSystem.SRGB: RGB_SPEC,
    ColorSystem.SRGB_LINEAR: RGB_SPEC,
    ColorSystem.DISPLAY_P3: RGB_SPEC,
    ColorSystem.DISPLAY_P3_LINEAR: RGB_SPEC,
    ColorSystem.A98_RGB: RGB_SPEC,
    ColorSystem.PROPHOTO_RGB: RGB_SPEC,
    ColorSystem.REC2020: RGB_SPEC,
    ColorSystem.XYZ_D65: XYZ_SPEC,
    ColorSystem.XYZ_D50: XYZ_SPEC,
    ColorSystem.HSL: HSL_SPEC,
    ColorSystem.HWB: HWB_SPEC,
    ColorSystem.LAB: LAB_SPEC,
    ColorSystem.OKLAB: LAB_SPEC,
    ColorSystem.LCH: LCH_SPEC,
    ColorSystem.OKLCH: LCH_SPEC,
}

HSL_EPSILON = 0.001
HWB_EPSILON = 99.999
LCH_EPSILON = 0.0015
OKLCH_EPSILON = 0.000004

POLAR_INTERPOLATION_SYSTEMS = {"lch", "oklch", "hsl", "hwb"}
InterpolationColorSystem = Literal[
    ColorSystem.SRGB, 
    ColorSystem.SRGB_LINEAR, 
    ColorSystem.DISPLAY_P3_LINEAR, 
    ColorSystem.XYZ_D65, 
    ColorSystem.XYZ_D50, 
    ColorSystem.LAB, 
    ColorSystem.OKLAB, 
    ColorSystem.LCH, 
    ColorSystem.OKLCH, 
    ColorSystem.HSL, 
    ColorSystem.HWB, 
]
INTERPOLATION_COLOR_SYSTEMS = tuple(InterpolationColorSystem.__args__)


class HueInterpolationMethod(StrEnum):
    SHORTER = "shorter"
    LONGER = "longer"
    INCREASING = "increasing"
    DECREASING = "decreasing"


def _hue_fixup(
    h1, h2, *, method: HueInterpolationMethod = HueInterpolationMethod.SHORTER
):
    h1 %= 360
    h2 %= 360
    match method:
        case HueInterpolationMethod.SHORTER:
            if h1 == h2:
                pass
            elif h2 - h1 > 180:
                h1 += 360
            elif h2 - h1 < -180:
                h2 += 360
        case HueInterpolationMethod.LONGER:
            if h1 == h2:
                h2 += 360
            elif 0 < h2 - h1 < 180:
                h1 += 360
            elif -180 < h2 - h1 < 0:
                h2 += 360
        case HueInterpolationMethod.INCREASING:
            if h2 < h1:
                h2 += 360
        case HueInterpolationMethod.DECREASING:
            if h1 < h2:
                h1 += 360
    return h1, h2


def _is_grey(system: ColorSystem, value) -> bool:
    match system:
        case "lch":
            L, C, h = value
            return C <= LCH_EPSILON or isnan(h)
        case "oklch":
            L, C, h = value
            return C <= OKLCH_EPSILON or isnan(h)
        case "hsl" | "hsv":
            h, s, l = value
            return s <= HSL_EPSILON or isnan(h)
        case "hwb":
            h, w, b = value
            return (w + b) >= HWB_EPSILON or isnan(h)
        case _:
            return False

def _to_grey(system: ColorSystem, value):
    match system:
        case "lch":
            L, C, h = value
            if C <= LCH_EPSILON:
                C = 0
                h = nan
            return L, C, h
        case "oklch":
            L, C, h = value
            if C <= OKLCH_EPSILON:
                C = 0
                h = nan
            return L, C, h
        case "hsl" | "hsv":
            h, s, l = value
            if s <= HSL_EPSILON:
                s = 0
                h = nan
            return h, s, l
        case "hwb":
            h, w, b = value
            if (w + b) >= HWB_EPSILON:
                # w = w / (w + b)
                # b = b / (w + b)
                h = nan
            return h, w, b
        case _:
            return value


def interpolate(
    interpolation: InterpolationColorSystem,
    proportion: FracOrFloat,
    system1: ColorSystem,
    values1: Tuple3,
    alpha1: FracOrFloat,
    system2: ColorSystem,
    values2: Tuple3,
    alpha2: FracOrFloat,
    *,
    hue_interpolation_method: HueInterpolationMethod = HueInterpolationMethod.SHORTER,
) -> tuple[Tuple3, FracOrFloat]:
    """Implements color interpolation.
    NOTE:
    - Only hue and alpha are supported as "missing components".
    - `nan` is used for missing hue or alpha.
    - Behavior is undefined if any other component is missing (`nan`).

    This is a deviation from CSS Color 4 where any component can be missing.
    """
    missing_alpha = False
    proportion1 = 1 - proportion
    match isnan(alpha1), isnan(alpha2):
        case False, False:
            pass
        case True, True:
            alpha1 = alpha2 = 1.0
            missing_alpha = True
        case True, False:
            alpha1 = alpha2
        case False, True:
            alpha2 = alpha1
    alpha = proportion1 * alpha1 + proportion * alpha2

    converted1 = convert(system1, interpolation, values1)
    converted2 = convert(system2, interpolation, values2)
    missing_hue1 = _is_grey(interpolation, converted1) or _is_grey(system1, values1)
    missing_hue2 = _is_grey(interpolation, converted2) or _is_grey(system2, values2)
    # if missing_hue1:
    #     converted1 = _to_grey(interpolation, converted1)
    # if missing_hue2:
    #     converted2 = _to_grey(interpolation, converted2)
    match interpolation:
        case ColorSystem.LCH | ColorSystem.OKLCH:
            L1, C1, h1 = converted1
            L2, C2, h2 = converted2
            L1 *= alpha1
            L2 *= alpha2
            C1 *= alpha1
            C2 *= alpha2
            match missing_hue1, missing_hue2:
                case False, False:
                    pass
                case True, False:
                    h1 = h2
                case False, True:
                    h2 = h1
                case True, True:
                    h1 = h2 = 0.0
            h1, h2 = _hue_fixup(h1, h2, method=hue_interpolation_method)
            L = proportion1 * L1 + proportion * L2
            C = proportion1 * C1 + proportion * C2
            h = proportion1 * h1 + proportion * h2
            h %= 360
            if (missing_hue1 and missing_hue2):
                h = nan
            if alpha == 0:
                return (L, C, h), 0.0
            elif missing_alpha:
                return (L, C, h), nan
            return (L / alpha, C / alpha, h), alpha
        case ColorSystem.HSL | ColorSystem.HWB:
            h1, s1, l1 = converted1
            h2, s2, l2 = converted2
            s1 *= alpha1
            s2 *= alpha2
            l1 *= alpha1
            l2 *= alpha2
            match missing_hue1, missing_hue2:
                case False, False:
                    pass
                case True, False:
                    h1 = h2
                case False, True:
                    h2 = h1
                case True, True:
                    h1 = h2 = 0.0
            h1, h2 = _hue_fixup(h1, h2, method=hue_interpolation_method)
            h = proportion1 * h1 + proportion * h2
            s = proportion1 * s1 + proportion * s2
            l = proportion1 * l1 + proportion * l2
            h %= 360
            if (missing_hue1 and missing_hue2):
                h = nan
            if alpha == 0:
                return (h, s, l), 0.0
            elif missing_alpha:
                return (h, s, l), nan
            return (h, s / alpha, l / alpha), alpha
        case _:
            r1, g1, b1 = vector_scalar_mul(converted1, alpha1)
            r2, g2, b2 = vector_scalar_mul(converted2, alpha2)
            r = proportion1 * r1 + proportion * r2
            g = proportion1 * g1 + proportion * g2
            b = proportion1 * b1 + proportion * b2
            if alpha == 0:
                return (r, g, b), 0.0
            elif missing_alpha:
                return (r, g, b), nan
            return (r / alpha, g / alpha, b / alpha), alpha


def relative_luminance(system: ColorSystem, values: Tuple3) -> FracOrFloat:
    """Returns the WCAG 2.1 relative luminance of the color.
    Out-of-gamut colors are gamut-mapped into the srgb-linear color system.
    """
    r, g, b = cast(Tuple3, convert_into_gamut(system, ColorSystem.SRGB_LINEAR, values))
    return clamp(0.2126 * r + 0.7152 * g + 0.0722 * b)


def wcag_2_1_contrast_ratio(
    system1: ColorSystem, values1: Tuple3, system2: ColorSystem, values2: Tuple3
):
    """Returns the WCAG 2.1 contrast ratio between two colors, between 1:1 and 21:1."""
    rl1 = relative_luminance(system1, values1)
    rl2 = relative_luminance(system2, values2)
    if rl1 >= rl2:
        return (rl1 + 0.05) / (rl2 + 0.05)
    return (rl2 + 0.05) / (rl1 + 0.05)
