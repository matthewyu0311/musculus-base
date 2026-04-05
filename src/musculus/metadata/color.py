# SPDX-License-Identifier: MIT
# See LICENSE, COPYING-W3C, COPYING-RGB for additional notes.

"""This module provides a class :class:`RGBAColor` which stores an RGBA value,
and provides a number of auxiliary methods based on the sRGB color model."""

from collections.abc import Iterable, Mapping
from fractions import Fraction
from functools import lru_cache
from types import MappingProxyType
from typing import Final, Literal, Self, cast, overload

from ..util.colorsystem import (
    ColorSystem,
    HueInterpolationMethod,
    InterpolationColorSystem,
    convert,
    interpolate,
)
from ..util.functions import (
    SlottedImmutableMixin,
    new_with_fields,
    runtime_final,
)
from ..util.number import (
    FracOrFloat,
    FracOrInt,
    clamp,
    css_round_towards_nearest_integer,
    frac,
    parse_css_angle,
    parse_percent,
)
from ..util.parse import (
    CSS_ARGUMENT_CHARS,
    Parseable,
    ValidityError,
    WellFormednessError,
    remove_ascii_spaces,
)

type ChannelOrder = Literal["ARGB", "RGB", "RGBA"]

# Ideally the LRU string cache size should be slightly greater than
# the number of reused instances (513 to be precise)
_LRU_STRINGS = 1024
_LRU_HEX = 1024

# The typical case involves 8 bits per channel
_LRU_BPC = 256
_0_4 = frac(4, 10)


@lru_cache(_LRU_BPC)
def _expand_bits(i: int, from_bits_per_channel: int, to_bits_per_channel: int):
    f = format(i, f"0{from_bits_per_channel}b")
    f *= to_bits_per_channel // from_bits_per_channel + 1
    return int(f[:to_bits_per_channel], base=2)


def _to_bits_per_channel(
    i: int, /, from_bits_per_channel: int, to_bits_per_channel: int
) -> int:
    if from_bits_per_channel == to_bits_per_channel:
        return i
    elif to_bits_per_channel > from_bits_per_channel:
        return _expand_bits(i, from_bits_per_channel, to_bits_per_channel)
    else:
        return i >> (from_bits_per_channel - to_bits_per_channel)


# These functions are not designed to handle complex input
# beyond those found in typical CSS color functions


def _css_read_rgb(rgb_source: str, /, default: FracOrInt = 0) -> FracOrInt:
    if not rgb_source or rgb_source == "none":
        return default
    try:
        return parse_percent(rgb_source, full_scale_100_percent=255) / 255
    except ValueError | ArithmeticError:
        # In parse contexts, raise either WellFormednessError or ValidityError
        raise WellFormednessError(f"Not a valid CSS value: {rgb_source!r}")


def _css_read_percent(
    percent_source: str,
    /,
    default: FracOrInt = 0,
    full_scale_100_percent: FracOrInt = 1,
) -> FracOrInt:
    if not percent_source or percent_source == "none":
        return default
    try:
        return parse_percent(
            percent_source, full_scale_100_percent=full_scale_100_percent
        )
    except ValueError | ArithmeticError:
        raise WellFormednessError(f"Not a valid CSS percent: {percent_source!r}")


def _css_read_alpha(
    alpha_source: str, /, default: FracOrInt = 1, none_default: FracOrInt = 0
) -> FracOrInt:
    if not alpha_source:
        return default
    if alpha_source == "none":
        return none_default
    try:
        return parse_percent(alpha_source)
    except ValueError | ArithmeticError:
        raise WellFormednessError(f"Not a valid CSS alpha: {alpha_source!r}")


def _css_read_hue(hue_source: str, /, default: FracOrInt = 0) -> FracOrInt:
    if not hue_source or hue_source == "none":
        return default
    try:
        return parse_css_angle(hue_source)
    except ValueError | ArithmeticError:
        raise WellFormednessError(f"Not a valid CSS angle: {hue_source!r}")


@runtime_final
class RGBAColor(SlottedImmutableMixin, Parseable):
    """An immutable class which stores a fixed-bit-count RGBA color value in the sRGB space,
    along the lines of CSS Color 3 (with the addition of HWB colors from CSS Color 4).

    The current implementation provides 8 bits per channel, for a total of 32 bits.

    Return an instance of :class:`RGBAColor` from an integer RGBA value.

    :param rgba: RGBA integer between 0 and :code:`MAX_RGBA_VALUE` inclusive.
        Bits higher than :code:`MAX_RGBA_VALUE` are discarded.
    :type rgba: int
    :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
        the uniqueness of identity of the instances returned.

    NOTE:
    * All instances, including :code:`RGBAColor(0x00000000)`, evaluate to `True` in boolean contexts.
    * Rich comparisons (such as :code:`__lt__,` :code:`__le__`) are defined to allow instances to
      sort among themselves somewhat reasonably in the RGBA order:
      :code:`RGBAColor(0xFF0000FE) < RGBAColor(0xFF0000FF) < RGBAColor(0xFF000100)`.
      Methods such as :code:`to_hslsvwb` provide information such as HSL, HSV and HWB which may be useful
      when designing custom sorting functions.
    * Like all other classes provided, no guarantees are made about the identity of the instances.
      Likewise, do not rely on the weak reference behavior of instances.
    """

    __slots__ = ("rgba",)
    #: The composite RGBA integer value, between 0 and :code:`MAX_RGBA_VALUE` inclusive.
    rgba: int

    #: Bits per channel as implemented by this class.
    BITS_PER_CHANNEL: Final[int] = 8

    #: Maximum channel value as implemented by this class.
    MAX_CHANNEL_VALUE: Final[int] = 2**BITS_PER_CHANNEL - 1

    #: Maximum RGBA integer value as implemented by this class.
    MAX_RGBA_VALUE: Final[int] = 2 ** (BITS_PER_CHANNEL * 4) - 1

    #: The four channels are exposed when using positional pattern matching.
    #: Use keyword patterns to match the composite RGBA integer value:
    #:
    #:     match value:
    #:         case RGBAColor(rgba):
    #:             ...
    #:         case RGBAColor(rgba=rgba):
    #:             ...
    #:         case RGBAColor(red=r, green=g, blue=b, alpha=a):
    #:             ...
    #:
    #: :meta public:
    __match_args__ = ("rgba",)

    @overload
    def __new__(cls, rgba: int) -> Self:
        """Return an instance of :class:`RGBAColor`. This class makse no guarantees of the identity of the returned instance."""
        pass

    @overload
    def __new__(
        cls, red: int, green: int, blue: int, alpha: int = MAX_CHANNEL_VALUE
    ) -> Self:
        """Return an instance of :class:`RGBAColor` from individual channel values.
        This class makse no guarantee of the identity of the returned instance.

        :param red: between 0 and :code:`MAX_CHANNEL_VALUE` inclusive, out-of-range values are clamped.
        :param green: between 0 and :code:`MAX_CHANNEL_VALUE` inclusive, out-of-range values are clamped.
        :param blue: between 0 and :code:`MAX_CHANNEL_VALUE` inclusive, out-of-range values are clamped.
        :param alpha: between 0 and :code:`MAX_CHANNEL_VALUE` inclusive, out-of-range values are clamped,
            defaults to :code:`MAX_CHANNEL_VALUE`.
        :type alpha: int, optional
        """
        pass

    @overload
    def __new__(
        cls,
        color: Self,
        /,
        *,
        red: int | None = None,
        green: int | None = None,
        blue: int | None = None,
        alpha: int | None = None,
    ) -> Self:
        """Replace constructor.

        :param red: Red channel, `None` to keep the value of the self instance.
        :param green: Green channel, `None` to keep the value of the self instance.
        :param blue: Blue channel, `None` to keep the value of the self instance.
        :param alpha: Alpha channel, `None` to keep the value of the self instance.
        :return: An instance of :class:`RGBAColor` with the specified channels replaced.
        """
        pass

    @overload
    def __new__(cls, source: str, /) -> Self:
        """Parse constructor. Does the same as `parse()`, except this provides no option to return `None`.

        :param source: String to be parsed with `parse()`.
        """
        pass

    def __new__(cls, *args, **kwargs) -> Self:
        match args, kwargs:
            case ([int(rgba)], {**other}) | (
                [],
                {"rgba": int(rgba), **other},
            ) if not other:
                rgba = cls.MAX_RGBA_VALUE & int(rgba)
            case ([RGBAColor(red=r, green=g, blue=b, alpha=a) as color], _):
                red = kwargs.get("red")
                if red is None:
                    red = r
                green = kwargs.get("green")
                if green is None:
                    green = g
                blue = kwargs.get("blue")
                if blue is None:
                    blue = b
                alpha = kwargs.get("alpha")
                if alpha is None:
                    alpha = a
                rgba = cls._rgba_from_channels(red, green, blue, alpha)
                if rgba == color.rgba:
                    assert isinstance(color, cls)
                    return color
            case ([str(source)], _):
                return cls.parse(source)
            case _:
                rgba = cls._rgba_from_channels(*args, **kwargs)
        return new_with_fields(cls, rgba=rgba)

    @classmethod
    def _rgba_from_channels(cls, red, green, blue, alpha=MAX_CHANNEL_VALUE) -> int:
        MAX_CHANNEL_VALUE = cls.MAX_CHANNEL_VALUE
        BITS_PER_CHANNEL = cls.BITS_PER_CHANNEL
        red = clamp(red, 0, MAX_CHANNEL_VALUE)
        green = clamp(green, 0, MAX_CHANNEL_VALUE)
        blue = clamp(blue, 0, MAX_CHANNEL_VALUE)
        alpha = clamp(alpha, 0, MAX_CHANNEL_VALUE)
        rgba = (
            (red << (BITS_PER_CHANNEL * 3))
            | (green << (BITS_PER_CHANNEL * 2))
            | (blue << BITS_PER_CHANNEL)
            | alpha
        )
        return rgba

    @property
    def red(self) -> int:
        """The red channel value, between 0 and :code:`MAX_CHANNEL_VALUE` inclusive."""
        return self.rgba >> (self.BITS_PER_CHANNEL * 3)

    @property
    def green(self) -> int:
        """The green channel value, between 0 and :code:`MAX_CHANNEL_VALUE` inclusive."""
        return (self.rgba >> self.BITS_PER_CHANNEL * 2) & self.MAX_CHANNEL_VALUE

    @property
    def blue(self) -> int:
        """The blue channel value, between 0 and :code:`MAX_CHANNEL_VALUE` inclusive."""
        return (self.rgba >> self.BITS_PER_CHANNEL) & self.MAX_CHANNEL_VALUE

    @property
    def alpha(self) -> int:
        """The alpha channel value, between 0 and :code:`MAX_CHANNEL_VALUE` inclusive."""
        return self.rgba & self.MAX_CHANNEL_VALUE

    def opacify(self) -> Self:
        """Return an opaque version of this color.

        :return: A color with maximum alpha, of Self if this color is already at maximum alpha.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        if self.alpha == MAX_CHANNEL_VALUE:
            return self
        return self.__class__(self, alpha=MAX_CHANNEL_VALUE)

    @classmethod
    def from_fractions(
        cls,
        red: FracOrFloat,
        green: FracOrFloat,
        blue: FracOrFloat,
        alpha: FracOrFloat = 1,
    ) -> Self:
        """Factory method that scales the input channel values and return an :class:`RGBAColor` instance.

        :param red: between zero and one inclusive, out-of-range values are clamped.
        :param green: between zero and one inclusive, out-of-range values are clamped.
        :param blue: between zero and one inclusive, out-of-range values are clamped.
        :param alpha: between zero and one inclusive, out-of-range values are clamped, defaults to one.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
        """
        MAX_CHANNEL_VALUE = cls.MAX_CHANNEL_VALUE
        r = css_round_towards_nearest_integer(clamp(red, 0, 1) * MAX_CHANNEL_VALUE)
        g = css_round_towards_nearest_integer(clamp(green, 0, 1) * MAX_CHANNEL_VALUE)
        b = css_round_towards_nearest_integer(clamp(blue, 0, 1) * MAX_CHANNEL_VALUE)
        a = css_round_towards_nearest_integer(clamp(alpha, 0, 1) * MAX_CHANNEL_VALUE)
        return cls(r, g, b, a)

    def to_fractions(self) -> tuple[FracOrInt, FracOrInt, FracOrInt, FracOrInt]:
        """Return the Fraction values for each of the four channels unpremultiplied.

        :return: A 4-tuple of `(red, green, blue, alpha)` scaled to between zero and one inclusive.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        return (
            frac(self.red, MAX_CHANNEL_VALUE),
            frac(self.green, MAX_CHANNEL_VALUE),
            frac(self.blue, MAX_CHANNEL_VALUE),
            frac(self.alpha, MAX_CHANNEL_VALUE),
        )

    def to_floats(self) -> tuple[float, float, float, float]:
        """Return the float values for each of the four channels unpremultiplied.
        This is primarily designed for use in external libraries such as Matplotlib.
        Use `from_fractions()` to convert the floats back into RGBAColor objects.

        :return: A 4-tuple of `(red, green, blue, alpha)` scaled to between between 0.0 and 1.0 inclusive.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        return (
            self.red / MAX_CHANNEL_VALUE,
            self.green / MAX_CHANNEL_VALUE,
            self.blue / MAX_CHANNEL_VALUE,
            self.alpha / MAX_CHANNEL_VALUE,
        )

    def to_premultiplied(self) -> tuple[Fraction, Fraction, Fraction, Fraction]:
        """Return the Fraction values for the three color channels, premultiplied by the alpha channel.
        This is useful for calculations involving additive colors.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        premul = frac(self.alpha, MAX_CHANNEL_VALUE)
        return (
            self.red * premul / MAX_CHANNEL_VALUE,
            self.green * premul / MAX_CHANNEL_VALUE,
            self.blue * premul / MAX_CHANNEL_VALUE,
            premul,
        )

    @classmethod
    def from_premultiplied(
        cls,
        red_premul: FracOrFloat,
        green_premul: FracOrFloat,
        blue_premul: FracOrFloat,
        alpha: FracOrFloat,
    ):
        if alpha == 0:
            red = red_premul
            green = green_premul
            blue = blue_premul
        else:
            red = red_premul / alpha
            green = green_premul / alpha
            blue = blue_premul / alpha
        return cls.from_fractions(red, green, blue, alpha)

    @classmethod
    def from_int(
        cls,
        i: int,
        /,
        *,
        bits_per_channel: int = BITS_PER_CHANNEL,
        channel_order: ChannelOrder = "RGBA",
    ) -> Self:
        """Process an integer returned from `to_int()`. Only the least significant bits are used.
        Unlike `from_hex`, the bits per channel is not constrained to multiples of 4.

        :param i: Integer value to be processed.
        :param bits_per_channel: Number of bits per channel, defaults to :code:`BITS_PER_CHANNEL`.
        :param channel_order: Channel order, defaults to "RGBA".
        :type channel_order: "RGB", "RGBA", "ARGB", optional
        :raises ValueError: If the channel order is unrecognized.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
        """
        MAX_CHANNEL_VALUE = cls.MAX_CHANNEL_VALUE
        # MAX_RGBA_VALUE = cls.MAX_RGBA_VALUE
        BITS_PER_CHANNEL = cls.BITS_PER_CHANNEL
        if bits_per_channel == BITS_PER_CHANNEL:
            if channel_order == "RGBA":
                return cls(i)
            elif channel_order == "RGB":
                return cls((i << BITS_PER_CHANNEL | MAX_CHANNEL_VALUE))
        # let channel order be 'wxyz'
        bm = 2**bits_per_channel - 1
        z = i & bm
        i >>= bits_per_channel
        y = i & bm
        i >>= bits_per_channel
        x = i & bm
        i >>= bits_per_channel
        w = i & bm
        v = (
            _to_bits_per_channel(
                n,
                from_bits_per_channel=bits_per_channel,
                to_bits_per_channel=BITS_PER_CHANNEL,
            )
            for n in (w, x, y, z)
        )
        match channel_order.upper():
            case "RGBA":
                r, g, b, a = v
            case "ARGB":
                a, r, g, b = v
            case "RGB":
                _, r, g, b = v
                a = MAX_CHANNEL_VALUE
            case _:
                raise ValueError(f"Unrecognized channel order: {channel_order!r}")
        return cls(
            (r << (BITS_PER_CHANNEL * 3))
            | (g << (BITS_PER_CHANNEL * 2))
            | (b << BITS_PER_CHANNEL)
            | a
        )

    def to_int(
        self,
        *,
        bits_per_channel: int = BITS_PER_CHANNEL,
        channel_order: ChannelOrder = "RGBA",
    ) -> int:
        """Return an integer value of all channels bitwise-ORed together according to the order.
        Channel values are widened or narrowed to between 0 and :code:`2 ** bits_per_channel - 1` inclusive.

        :param bits_per_channel: Number of bits per channel, defaults to :code:`BITS_PER_CHANNEL`.
        :type bits_per_channel: int, optional
        :param channel_order: Channel order, defaults to "RGBA".
        :type channel_order: str "RGB", "RGBA", "ARGB", optional
        :raises ValueError: If the channel order is unrecognized.
        :return: An integer value of all channels.
        """
        BITS_PER_CHANNEL = self.BITS_PER_CHANNEL
        if channel_order == "RGBA" and bits_per_channel == BITS_PER_CHANNEL:
            return self.rgba

        r_b = _to_bits_per_channel(
            self.red,
            from_bits_per_channel=BITS_PER_CHANNEL,
            to_bits_per_channel=bits_per_channel,
        )
        g_b = _to_bits_per_channel(
            self.green,
            from_bits_per_channel=BITS_PER_CHANNEL,
            to_bits_per_channel=bits_per_channel,
        )
        b_b = _to_bits_per_channel(
            self.blue,
            from_bits_per_channel=BITS_PER_CHANNEL,
            to_bits_per_channel=bits_per_channel,
        )
        a_b = _to_bits_per_channel(
            self.alpha,
            from_bits_per_channel=BITS_PER_CHANNEL,
            to_bits_per_channel=bits_per_channel,
        )
        match channel_order.upper():
            case "RGBA":
                result = r_b
                result <<= bits_per_channel
                result |= g_b
                result <<= bits_per_channel
                result |= b_b
                result <<= bits_per_channel
                result |= a_b
            case "ARGB":
                result = a_b
                result <<= bits_per_channel
                result |= r_b
                result <<= bits_per_channel
                result |= g_b
                result <<= bits_per_channel
                result |= b_b
            case "RGB":
                result = r_b
                result <<= bits_per_channel
                result |= g_b
                result <<= bits_per_channel
                result |= b_b
            case _:
                raise ValueError(f"Unrecognized channel order: {channel_order!r}")
        return result

    @classmethod
    def from_hex(
        cls,
        source: str,
        /,
        *,
        bits_per_channel: int = BITS_PER_CHANNEL,
        channel_order: ChannelOrder = "RGBA",
    ) -> Self:
        """Parse a hexadecimal color code, starting with U+0023 NUMBER SIGN (#),
        followed by ASCII hexadecimal digits.

        :param source: The string to be parsed.
        :type source: str
        :param bits_per_channel: Number of bits per channel, defaults to :code:`BITS_PER_CHANNEL`.
        :type bits_per_channel: int, optional
        :param channel_order: Channel order, defaults to "RGBA".
        :type channel_order: str "RGB", "RGBA", "ARGB", optional
        :raises ValueError: If the source is not an ASCII string in a proper `#hexadecimal` format.
        :raises ValueError: If the channel order is unrecognized.
        :raises ValueError: If bits per channel is not a positive multiple of 4.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
        """
        if not source.isascii():
            raise WellFormednessError(f"Not in ASCII: {source!r}")
        if bits_per_channel % 4 or bits_per_channel <= 0:
            raise ValueError(f"Bits per channel not multiple of 4: {bits_per_channel}")
        actual_length = len(source)
        expected_length = (bits_per_channel * len(channel_order)) // 4 + 1
        if expected_length != actual_length:
            raise WellFormednessError(
                f"Expected {expected_length} characters, got {actual_length}: {source!r}"
            )
        if not source[1:].isalnum() or source[0] != "#":
            raise WellFormednessError(f"Not in #hexadecimal format: {source!r}")
        s = source[1:]
        return cls.from_int(
            int(s, base=16),
            bits_per_channel=bits_per_channel,
            channel_order=channel_order,
        )

    @lru_cache(maxsize=_LRU_HEX)
    def to_hex_rrggbb(self) -> str:
        """Return the `#rrggbb` hexadecimal string of the color with prefix "#".

        :return: A string such as `#c3aacc`, ignoring alpha.
        """
        return f"#{self.to_int(bits_per_channel=8, channel_order='RGB'):06x}"

    @lru_cache(maxsize=_LRU_HEX)
    def to_hex_rrggbbaa(self) -> str:
        """Return the `#rrggbbaa` hexadecimal string of the color with prefix "#".

        :return: A string such as `#c3aaccee`, always with alpha.
        """
        return f"#{self.to_int(bits_per_channel=8, channel_order='RGBA'):08x}"

    __int__ = __index__ = to_int

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(0x{self.to_hex_rrggbbaa()[1:]})"

    def __bool__(self) -> Literal[True]:
        """All instances, including `RGBAColor(0x00000000)`, evaluate to `True`
        in boolean contexts, even if `int(RGBAColor(0x00000000))` returns 0.

        The reason for this behavior is that CSS has a definition of what "no value"
        means ("none" is the generic CSS keyword and would have been represented as `None`,
        which is outside the scope of this class). On the other hand,
        `#00000000` (`transparent`) is a valid color value which behaves just like any other color.

        Applications expecting needing to special-case null values or fully-transparent colors
        must handle them separately.
        :return: Always return `True`, which shall be understood as that a color value
        has been specified (even if the color may be transparent).
        """
        # Since we have provided a custom __int__, we need to override the __bool__
        return True

    @lru_cache(maxsize=_LRU_STRINGS)
    def __str__(self) -> str:
        """Return the `#rrggbb` or `#rrggbbaa` hexadecimal string of the color with prefix "#".

        :return: A string such as `#c3aaccee`, or `#c3aacc` if the alpha value is 0xFF.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        if self.alpha == MAX_CHANNEL_VALUE:
            return self.to_hex_rrggbb()
        return self.to_hex_rrggbbaa()

    @lru_cache(maxsize=_LRU_STRINGS)
    def __format__(self, format_spec: str) -> str:
        """Returns a formatted string.

        The format specification of :class:`RGBAColor` is special and consists of:
        * `R`, `r`: hexadecimal digits of the red channel
        * `G`, `g`: hexadecimal digits of the green channel
        * `B`, `b`: hexadecimal digits of the blue channel
        * `A`, `a`: hexadecimal digits of the alpha channel

        The case of the hexdecimal digits are preserved.
        Channel width is determined from the number of digits supplied.
        All other characters in the format specification string are passed through unchanged.

        For example,
        `format(RGBAColor.parse("#ff0000ff"), "#AARRGGBB")` returns "#FFFF0000", and
        `format(RGBAColor.parse("#fedcba"), "#argbARGB")` returns "#ffdbFECA".

        This syntax can also be used in f-strings.
        `f"Red: {color:RR}, Green: {color:GG}, Blue: {color:BB}, Alpha: {color:AA}"`
        will produce results such as "Red: 80, Green: 40, Blue: 20, Alpha: FF".

        :param format_spec: Format specification string.
        :type format_spec: str
        :return: The formatted string, or the result of `str()` if empty.
        """
        if not format_spec:
            return str(self)
        r_bits = g_bits = b_bits = a_bits = 0
        for c in format_spec:
            match c:
                case "R" | "r":
                    r_bits += 4
                case "G" | "g":
                    g_bits += 4
                case "B" | "b":
                    b_bits += 4
                case "A" | "a":
                    a_bits += 4
                case _:
                    pass
        rs = gs = bs = alphas = ""
        if r_bits:
            r = _to_bits_per_channel(
                self.red,
                from_bits_per_channel=self.BITS_PER_CHANNEL,
                to_bits_per_channel=r_bits,
            )
            rs = format(r, f"0{r_bits // 4}x")
            rc = iter(rs)
        if g_bits:
            g = _to_bits_per_channel(
                self.green,
                from_bits_per_channel=self.BITS_PER_CHANNEL,
                to_bits_per_channel=g_bits,
            )
            gs = format(g, f"0{g_bits // 4}x")
            gc = iter(gs)
        if b_bits:
            b = _to_bits_per_channel(
                self.blue,
                from_bits_per_channel=self.BITS_PER_CHANNEL,
                to_bits_per_channel=b_bits,
            )
            bs = format(b, f"0{b_bits // 4}x")
            bc = iter(bs)
        if a_bits:
            a = _to_bits_per_channel(
                self.alpha,
                from_bits_per_channel=self.BITS_PER_CHANNEL,
                to_bits_per_channel=a_bits,
            )
            alphas = format(a, f"0{a_bits // 4}x")
            ac = iter(alphas)
        output = []
        for c in format_spec:
            try:
                match c:
                    case "R":
                        output.append(next(rc).upper())
                    case "r":
                        output.append(next(rc))
                    case "G":
                        output.append(next(gc).upper())
                    case "g":
                        output.append(next(gc))
                    case "B":
                        output.append(next(bc).upper())
                    case "b":
                        output.append(next(bc))
                    case "A":
                        output.append(next(ac).upper())
                    case "a":
                        output.append(next(ac))
                    case char:
                        # Characters outside of [RrGgBbAa] are output as-is
                        output.append(char)
            except StopIteration:
                # This should NEVER happen
                # (Getting fewer digits from format string than specified)
                raise AssertionError(f"Bits per channel mismatch in __format__")
        return "".join(output)

    @classmethod
    def from_qt(cls, source: str, /) -> Self:
        """Parse a string in the fashion of Qt `QColor::fromString`.
        Refer to https://doc.qt.io/qt-6/qcolor.html#fromString for its documentation.

        Accepts the hexadecimal #RGB forms of 3, 6, 9 and 12 hexadecimal foms, and the #AARRGGBB form,
        and named colors.

        :param source: String to be parsed.
        :type source: str
        :raises ValueError: If source is not a valid Qt color string.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
        """
        s = source.strip().casefold()
        if not s:
            raise WellFormednessError("Source is empty or whitespace")
        if s[0] == "#":
            match len(s) - 1:
                case 3:
                    order = "RGB"
                    bits_per_channel = 4
                case 6:
                    order = "RGB"
                    bits_per_channel = 8
                case 8:
                    order = "ARGB"
                    bits_per_channel = 8
                case 9:
                    order = "RGB"
                    bits_per_channel = 12
                case 12:
                    order = "RGB"
                    bits_per_channel = 16
                case _:
                    raise WellFormednessError(
                        f"Wrong number of Qt hexadecimal color digits: {s}"
                    )
            return cls.from_hex(
                s, bits_per_channel=bits_per_channel, channel_order=order
            )
        try:
            return cls(cls.SVG_NAMES[s])
        except KeyError:
            raise ValidityError(f"Not a Qt color: {s!r}")

    def to_qt(self) -> str:
        """Return the `#rrggbb` or `#aarrggbb` form, whichever is shorter,
        suitable for use in Qt QColor::fromString

        :return: A hexadecimal string.
        """
        MAX_CHANNEL_VALUE = self.MAX_CHANNEL_VALUE
        if self.alpha == MAX_CHANNEL_VALUE:
            return self.to_hex_rrggbb()
        return f"#{self.to_int(bits_per_channel=8, channel_order='ARGB'):08x}"

    @classmethod
    def from_model(
        cls,
        model: ColorSystem,
        values: Iterable[FracOrFloat],
        alpha: FracOrFloat = 1,
    ) -> Self:
        model = ColorSystem(model.casefold())
        r, g, b = convert(model, ColorSystem.SRGB, values)
        return cls.from_fractions(r, g, b, alpha=alpha)

    def to_model(self, model: ColorSystem | str) -> tuple[FracOrFloat, ...]:
        r, g, b, _ = self.to_fractions()
        model = ColorSystem(model.casefold())
        return tuple(convert(ColorSystem.SRGB, model, (r, g, b)))

    def interpolate(
        self,
        proportion: FracOrFloat,
        other: RGBAColor,
        *,
        interpolation: InterpolationColorSystem = ColorSystem.OKLAB,
        hue_interpolation_method: HueInterpolationMethod = HueInterpolationMethod.SHORTER,
    ) -> RGBAColor:
        fl1 = self.to_floats()
        fl2 = other.to_floats()
        result, alpha = interpolate(
            interpolation,
            proportion,
            system1=ColorSystem.SRGB,
            values1=fl1[0:3],
            alpha1=fl1[3],
            system2=ColorSystem.SRGB,
            values2=fl2[0:3],
            alpha2=fl2[3],
            hue_interpolation_method=hue_interpolation_method,
        )
        return self.__class__.from_model(
            interpolation,
            result,
            alpha,
        )

    @classmethod
    def from_x11_name(cls, x11_name: str, /) -> Self:
        """Return an instance corresponding to an X11 color name.

        :param x11_name: Input must be in ASCII. Whitespaces and case are not significant.
        :type x11_name: str
        :raises ValueError: If the input is not a valid X11 color name.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
        """
        try:
            # If it works on first pass we can save a collation step
            return cls(cls.X11_NAMES[x11_name])
        except KeyError:
            s = remove_ascii_spaces(x11_name).casefold()
            try:
                return cls(cls.X11_NAMES_COLLATED[s])
            except KeyError:
                raise ValidityError(f"Not an X11 color: {x11_name!r}")

    def to_x11_name(self) -> str | None:
        """Return any of the X11 names of the color after coercing into 8 bits per channel,
        or `None` if not named in X11 or if the color has a non-maximum alpha channel.

        :return: X11 color name or `None` if not named.
        """
        return self.X11_NAMES_INVERSE.get(self.rgba, None)

    @classmethod
    def _from_css_function(cls, source: str, /) -> Self:
        if not source.isascii():
            raise WellFormednessError(
                f"CSS sRGB color function not in ASCII: {source!r}"
            )

        # Strip aggressively as CSS allows many whitespaces
        fname, bracket, content = source.strip().casefold().partition("(")
        fname = fname.rstrip()
        if not bracket or content[-1] != ")":
            raise WellFormednessError(
                f"Unrecognized bracket pattern in CSS sRGB color function: {source!r}"
            )
        # Remove the final ")""
        content = content[:-1]
        # Replace all delimiters with spaces
        content = content.replace("/", " ").replace(",", " ")
        if not all(c in CSS_ARGUMENT_CHARS or c.isspace() for c in content):
            raise WellFormednessError(
                f"Unrecognized character in CSS sRGB color function: {source!r}"
            )
        # Collapse consecutive spaces into separate arguments
        arguments = content.split()
        match len(arguments):
            case 3:
                a = 1
            case 4:
                a = _css_read_alpha(arguments[3])
            case _:
                raise WellFormednessError(
                    f"CSS sRGB color function takes 3 or 4 arguments: {source!r}"
                )
        match fname:
            case "rgb" | "rgba":
                r = _css_read_rgb(arguments[0])
                g = _css_read_rgb(arguments[1])
                b = _css_read_rgb(arguments[2])
                return cls.from_fractions(red=r, green=g, blue=b, alpha=a)
            case "hsl" | "hsla" | "hsv" | "hsva" | "hwb":
                hue = _css_read_hue(arguments[0])
                second = _css_read_percent(arguments[1], full_scale_100_percent=100)
                third = _css_read_percent(arguments[2], full_scale_100_percent=100)
                fname = cast(ColorSystem, fname[0:3])
                return cls.from_model(ColorSystem(fname), (hue, second, third), alpha=a)
            case "lab":
                L = clamp(
                    _css_read_percent(arguments[0], full_scale_100_percent=100), 0, 100
                )
                a = _css_read_percent(arguments[1], full_scale_100_percent=125)
                b = _css_read_percent(arguments[2], full_scale_100_percent=125)
                return cls.from_model(ColorSystem.LAB, (L, a, b), alpha=a)
            case "oklab":
                L = clamp(
                    _css_read_percent(arguments[0], full_scale_100_percent=1), 0, 1
                )
                a = _css_read_percent(arguments[1], full_scale_100_percent=_0_4)
                b = _css_read_percent(arguments[2], full_scale_100_percent=_0_4)
                return cls.from_model(ColorSystem.OKLAB, (L, a, b), alpha=a)
            case "lch":
                L = clamp(
                    _css_read_percent(arguments[0], full_scale_100_percent=100), 0, 100
                )
                C = _css_read_percent(arguments[1], full_scale_100_percent=150)
                h = _css_read_hue(arguments[2])
                return cls.from_model(ColorSystem.LCH, (L, C, h), alpha=a)
            case "oklch":
                L = clamp(
                    _css_read_percent(arguments[0], full_scale_100_percent=1), 0, 1
                )
                C = _css_read_percent(arguments[1], full_scale_100_percent=_0_4)
                h = _css_read_hue(arguments[2])
                return cls.from_model(ColorSystem.OKLCH, (L, C, h), alpha=a)
            case _:
                raise WellFormednessError(f"Not a CSS sRGB color function: {source!r}")

    @classmethod
    @overload
    def from_css(cls, source: str, /, allow_none: Literal[False] = False) -> Self: ...

    @classmethod
    @overload
    def from_css(cls, source: str, /, allow_none: bool) -> Self | None: ...

    @classmethod
    def from_css(cls, source: str, /, allow_none: bool = False) -> Self | None:
        """Parse a source string in the hexadecimal form, SVG color names (CSS color keywords)
        and CSS color functions.

        The color names supported are the SVG 1.0 names:

        * `transparent` is supported as `#00000000`.
        * Color names that appear in both SVG and X11 resolve to the SVG values, not the X11 values.
        * System colors and `currentColor` are not supported.

        A limited number of CSS Color 3 and 4 features are available:
        * The sRGB color functions `rgb[a]()`, `hsl[a]()` and `hwb()` are supported.
        * Comma-separated `rgb(255,24,77)` and space-separated forms `rgb(255 24 77)`
          are supported.
        * Mixed units and separators `hsl(270deg, 30% 0.5/1)` are supported.

        Certain features differ from CSS:
        * HSV color is not specified in CSS, but is available as `hsv[a]()` for symmetry.
        * Non-sRGB colors are not supported.
        * Arithmetic operations such as `calc()` are not supported.

        :param source: A valid CSS sRGB color, case-insensitive, must be in ASCII.
        :type source: str
        :param allow_none: If true, return None if an empty value or "none" is encountered,
            instead of raising `ValueError` (the default behavior)
        :raises ValueError: If the source cannot be parsed as a valid CSS sRGB color.
        :raises ValueError: If the source is empty, whitespace-only or not in ASCII.
        :raises ValueError: If the number of CSS hexadecimal color digits is not 3, 4, 6 or 8.
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
            `None` may be returned if `allow_none` is true.
        """
        if not source.isascii():
            raise WellFormednessError(f"CSS color not in ASCII: {source!r}")
        s = source.strip().casefold()
        if not s:
            if allow_none:
                return None
            raise WellFormednessError("Source is empty or whitespace")
        if s == "none":
            if allow_none:
                return None
            raise ValidityError("None is not allowed")
        if s[0] == "#":
            match len(s) - 1:
                case 3:
                    order = "RGB"
                    bits_per_channel = 4
                case 4:
                    order = "RGBA"
                    bits_per_channel = 4
                case 6:
                    order = "RGB"
                    bits_per_channel = 8
                case 8:
                    order = "RGBA"
                    bits_per_channel = 8
                case _:
                    raise WellFormednessError(
                        f"Wrong number of CSS hexadecimal color digits: {s}"
                    )
            return cls.from_hex(
                s, bits_per_channel=bits_per_channel, channel_order=order
            )
        try:
            return cls(cls.SVG_NAMES[s])
        except KeyError:
            pass
        try:
            return cls._from_css_function(s)
        except KeyError:
            pass
        raise ValidityError(f"Not a valid CSS sRGB color: {s!r}")

    def to_svg_name_or_hex(self) -> str:
        """Return any of the SVG names, such as `red`, `#rrggbb` or `#rrggbbaa`, in that order of preference.

        :return: An SVG color name or hexadecimal code.
        """
        try:
            return self.SVG_NAMES_INVERSE[self.rgba]
        except KeyError:
            return str(self)

    @classmethod
    @overload
    def parse(cls, source: str, /, allow_none: Literal[False] = False) -> Self: ...

    @classmethod
    @overload
    def parse(cls, source: str, /, allow_none: bool) -> Self | None: ...

    @classmethod
    def parse(cls, source: str, /, allow_none: bool = False) -> Self | None:
        """Parse a color string, in hexadecimal, SVG names, CSS functions and X11 name forms,
        in that order of preference. Accepts all inputs to the :code:`from_css` and :code:`from_x11_name` methods.

        :param source: A color name, CSS function or hexadecimal string.
        :type source: str
        :param allow_none: If true, return `None` if an empty value or "none" is encountered,
            instead of raising `ValueError` (the default behavior).
        :type allow_none: bool
        :return: An instance of :class:`RGBAColor`. This class makes no guarantees regarding
            the uniqueness of identity of the instances returned.
            `None` may be returned if `allow_none` is true.
        """
        if not source.isascii():
            raise WellFormednessError(f"CSS color not in ASCII: {source!r}")
        s = source.strip().casefold()
        if not s:
            if allow_none:
                return None
            raise WellFormednessError("Source is empty or whitespace")
        if s == "none":
            if allow_none:
                return None
            raise ValidityError("None is not allowed")
        try:
            return cls.from_css(s)
        except ValueError:
            return cls.from_x11_name(s)

    SVG_NAMES: Final[Mapping[str, int]] = MappingProxyType(
        {
            "transparent": 0x00000000,
            "aliceblue": 0xF0F8FFFF,
            "antiquewhite": 0xFAEBD7FF,
            "aqua": 0x00FFFFFF,
            "aquamarine": 0x7FFFD4FF,
            "azure": 0xF0FFFFFF,
            "beige": 0xF5F5DCFF,
            "bisque": 0xFFE4C4FF,
            "black": 0x000000FF,
            "blanchedalmond": 0xFFEBCDFF,
            "blue": 0x0000FFFF,
            "blueviolet": 0x8A2BE2FF,
            "brown": 0xA52A2AFF,
            "burlywood": 0xDEB887FF,
            "cadetblue": 0x5F9EA0FF,
            "chartreuse": 0x7FFF00FF,
            "chocolate": 0xD2691EFF,
            "coral": 0xFF7F50FF,
            "cornflowerblue": 0x6495EDFF,
            "cornsilk": 0xFFF8DCFF,
            "crimson": 0xDC143CFF,
            "cyan": 0x00FFFFFF,
            "darkblue": 0x00008BFF,
            "darkcyan": 0x008B8BFF,
            "darkgoldenrod": 0xB8860BFF,
            "darkgray": 0xA9A9A9FF,
            "darkgrey": 0xA9A9A9FF,
            "darkgreen": 0x006400FF,
            "darkkhaki": 0xBDB76BFF,
            "darkmagenta": 0x8B008BFF,
            "darkolivegreen": 0x556B2FFF,
            "darkorange": 0xFF8C00FF,
            "darkorchid": 0x9932CCFF,
            "darkred": 0x8B0000FF,
            "darksalmon": 0xE9967AFF,
            "darkseagreen": 0x8FBC8FFF,
            "darkslateblue": 0x483D8BFF,
            "darkslategray": 0x2F4F4FFF,
            "darkslategrey": 0x2F4F4FFF,
            "darkturquoise": 0x00CED1FF,
            "darkviolet": 0x9400D3FF,
            "deeppink": 0xFF1493FF,
            "deepskyblue": 0x00BFFFFF,
            "dimgray": 0x696969FF,
            "dimgrey": 0x696969FF,
            "dodgerblue": 0x1E90FFFF,
            "firebrick": 0xB22222FF,
            "floralwhite": 0xFFFAF0FF,
            "forestgreen": 0x228B22FF,
            "fuchsia": 0xFF00FFFF,
            "gainsboro": 0xDCDCDCFF,
            "ghostwhite": 0xF8F8FFFF,
            "gold": 0xFFD700FF,
            "goldenrod": 0xDAA520FF,
            "gray": 0x808080FF,
            "grey": 0x808080FF,
            "green": 0x008000FF,
            "greenyellow": 0xADFF2FFF,
            "honeydew": 0xF0FFF0FF,
            "hotpink": 0xFF69B4FF,
            "indianred": 0xCD5C5CFF,
            "indigo": 0x4B0082FF,
            "ivory": 0xFFFFF0FF,
            "khaki": 0xF0E68CFF,
            "lavender": 0xE6E6FAFF,
            "lavenderblush": 0xFFF0F5FF,
            "lawngreen": 0x7CFC00FF,
            "lemonchiffon": 0xFFFACDFF,
            "lightblue": 0xADD8E6FF,
            "lightcoral": 0xF08080FF,
            "lightcyan": 0xE0FFFFFF,
            "lightgoldenrodyellow": 0xFAFAD2FF,
            "lightgray": 0xD3D3D3FF,
            "lightgrey": 0xD3D3D3FF,
            "lightgreen": 0x90EE90FF,
            "lightpink": 0xFFB6C1FF,
            "lightsalmon": 0xFFA07AFF,
            "lightseagreen": 0x20B2AAFF,
            "lightskyblue": 0x87CEFAFF,
            "lightslategray": 0x778899FF,
            "lightslategrey": 0x778899FF,
            "lightsteelblue": 0xB0C4DEFF,
            "lightyellow": 0xFFFFE0FF,
            "lime": 0x00FF00FF,
            "limegreen": 0x32CD32FF,
            "linen": 0xFAF0E6FF,
            "magenta": 0xFF00FFFF,
            "maroon": 0x800000FF,
            "mediumaquamarine": 0x66CDAAFF,
            "mediumblue": 0x0000CDFF,
            "mediumorchid": 0xBA55D3FF,
            "mediumpurple": 0x9370DBFF,
            "mediumseagreen": 0x3CB371FF,
            "mediumslateblue": 0x7B68EEFF,
            "mediumspringgreen": 0x00FA9AFF,
            "mediumturquoise": 0x48D1CCFF,
            "mediumvioletred": 0xC71585FF,
            "midnightblue": 0x191970FF,
            "mintcream": 0xF5FFFAFF,
            "mistyrose": 0xFFE4E1FF,
            "moccasin": 0xFFE4B5FF,
            "navajowhite": 0xFFDEADFF,
            "navy": 0x000080FF,
            "oldlace": 0xFDF5E6FF,
            "olive": 0x808000FF,
            "olivedrab": 0x6B8E23FF,
            "orange": 0xFFA500FF,
            "orangered": 0xFF4500FF,
            "orchid": 0xDA70D6FF,
            "palegoldenrod": 0xEEE8AAFF,
            "palegreen": 0x98FB98FF,
            "paleturquoise": 0xAFEEEEFF,
            "palevioletred": 0xDB7093FF,
            "papayawhip": 0xFFEFD5FF,
            "peachpuff": 0xFFDAB9FF,
            "peru": 0xCD853FFF,
            "pink": 0xFFC0CBFF,
            "plum": 0xDDA0DDFF,
            "powderblue": 0xB0E0E6FF,
            "purple": 0x800080FF,
            "rebeccapurple": 0x663399FF,
            "red": 0xFF0000FF,
            "rosybrown": 0xBC8F8FFF,
            "royalblue": 0x4169E1FF,
            "saddlebrown": 0x8B4513FF,
            "salmon": 0xFA8072FF,
            "sandybrown": 0xF4A460FF,
            "seagreen": 0x2E8B57FF,
            "seashell": 0xFFF5EEFF,
            "sienna": 0xA0522DFF,
            "silver": 0xC0C0C0FF,
            "skyblue": 0x87CEEBFF,
            "slateblue": 0x6A5ACDFF,
            "slategray": 0x708090FF,
            "slategrey": 0x708090FF,
            "snow": 0xFFFAFAFF,
            "springgreen": 0x00FF7FFF,
            "steelblue": 0x4682B4FF,
            "tan": 0xD2B48CFF,
            "teal": 0x008080FF,
            "thistle": 0xD8BFD8FF,
            "tomato": 0xFF6347FF,
            "turquoise": 0x40E0D0FF,
            "violet": 0xEE82EEFF,
            "wheat": 0xF5DEB3FF,
            "white": 0xFFFFFFFF,
            "whitesmoke": 0xF5F5F5FF,
            "yellow": 0xFFFF00FF,
            "yellowgreen": 0x9ACD32FF,
        }
    )
    SVG_NAMES_INVERSE: Final[Mapping[int, str]] = MappingProxyType(
        {_v: _k for _k, _v in SVG_NAMES.items()}
    )

    X11_NAMES: Final[Mapping[str, int]] = {
        "snow": 0xFFFAFAFF,
        "ghost white": 0xF8F8FFFF,
        "GhostWhite": 0xF8F8FFFF,
        "white smoke": 0xF5F5F5FF,
        "WhiteSmoke": 0xF5F5F5FF,
        "gainsboro": 0xDCDCDCFF,
        "floral white": 0xFFFAF0FF,
        "FloralWhite": 0xFFFAF0FF,
        "old lace": 0xFDF5E6FF,
        "OldLace": 0xFDF5E6FF,
        "linen": 0xFAF0E6FF,
        "antique white": 0xFAEBD7FF,
        "AntiqueWhite": 0xFAEBD7FF,
        "papaya whip": 0xFFEFD5FF,
        "PapayaWhip": 0xFFEFD5FF,
        "blanched almond": 0xFFEBCDFF,
        "BlanchedAlmond": 0xFFEBCDFF,
        "bisque": 0xFFE4C4FF,
        "peach puff": 0xFFDAB9FF,
        "PeachPuff": 0xFFDAB9FF,
        "navajo white": 0xFFDEADFF,
        "NavajoWhite": 0xFFDEADFF,
        "moccasin": 0xFFE4B5FF,
        "cornsilk": 0xFFF8DCFF,
        "ivory": 0xFFFFF0FF,
        "lemon chiffon": 0xFFFACDFF,
        "LemonChiffon": 0xFFFACDFF,
        "seashell": 0xFFF5EEFF,
        "honeydew": 0xF0FFF0FF,
        "mint cream": 0xF5FFFAFF,
        "MintCream": 0xF5FFFAFF,
        "azure": 0xF0FFFFFF,
        "alice blue": 0xF0F8FFFF,
        "AliceBlue": 0xF0F8FFFF,
        "lavender": 0xE6E6FAFF,
        "lavender blush": 0xFFF0F5FF,
        "LavenderBlush": 0xFFF0F5FF,
        "misty rose": 0xFFE4E1FF,
        "MistyRose": 0xFFE4E1FF,
        "white": 0xFFFFFFFF,
        "black": 0x000000FF,
        "dark slate gray": 0x2F4F4FFF,
        "DarkSlateGray": 0x2F4F4FFF,
        "dark slate grey": 0x2F4F4FFF,
        "DarkSlateGrey": 0x2F4F4FFF,
        "dim gray": 0x696969FF,
        "DimGray": 0x696969FF,
        "dim grey": 0x696969FF,
        "DimGrey": 0x696969FF,
        "slate gray": 0x708090FF,
        "SlateGray": 0x708090FF,
        "slate grey": 0x708090FF,
        "SlateGrey": 0x708090FF,
        "light slate gray": 0x778899FF,
        "LightSlateGray": 0x778899FF,
        "light slate grey": 0x778899FF,
        "LightSlateGrey": 0x778899FF,
        "gray": 0xBEBEBEFF,
        "grey": 0xBEBEBEFF,
        "x11 gray": 0xBEBEBEFF,
        "X11Gray": 0xBEBEBEFF,
        "x11 grey": 0xBEBEBEFF,
        "X11Grey": 0xBEBEBEFF,
        "web gray": 0x808080FF,
        "WebGray": 0x808080FF,
        "web grey": 0x808080FF,
        "WebGrey": 0x808080FF,
        "light grey": 0xD3D3D3FF,
        "LightGrey": 0xD3D3D3FF,
        "light gray": 0xD3D3D3FF,
        "LightGray": 0xD3D3D3FF,
        "midnight blue": 0x191970FF,
        "MidnightBlue": 0x191970FF,
        "navy": 0x000080FF,
        "navy blue": 0x000080FF,
        "NavyBlue": 0x000080FF,
        "cornflower blue": 0x6495EDFF,
        "CornflowerBlue": 0x6495EDFF,
        "dark slate blue": 0x483D8BFF,
        "DarkSlateBlue": 0x483D8BFF,
        "slate blue": 0x6A5ACDFF,
        "SlateBlue": 0x6A5ACDFF,
        "medium slate blue": 0x7B68EEFF,
        "MediumSlateBlue": 0x7B68EEFF,
        "light slate blue": 0x8470FFFF,
        "LightSlateBlue": 0x8470FFFF,
        "medium blue": 0x0000CDFF,
        "MediumBlue": 0x0000CDFF,
        "royal blue": 0x4169E1FF,
        "RoyalBlue": 0x4169E1FF,
        "blue": 0x0000FFFF,
        "dodger blue": 0x1E90FFFF,
        "DodgerBlue": 0x1E90FFFF,
        "deep sky blue": 0x00BFFFFF,
        "DeepSkyBlue": 0x00BFFFFF,
        "sky blue": 0x87CEEBFF,
        "SkyBlue": 0x87CEEBFF,
        "light sky blue": 0x87CEFAFF,
        "LightSkyBlue": 0x87CEFAFF,
        "steel blue": 0x4682B4FF,
        "SteelBlue": 0x4682B4FF,
        "light steel blue": 0xB0C4DEFF,
        "LightSteelBlue": 0xB0C4DEFF,
        "light blue": 0xADD8E6FF,
        "LightBlue": 0xADD8E6FF,
        "powder blue": 0xB0E0E6FF,
        "PowderBlue": 0xB0E0E6FF,
        "pale turquoise": 0xAFEEEEFF,
        "PaleTurquoise": 0xAFEEEEFF,
        "dark turquoise": 0x00CED1FF,
        "DarkTurquoise": 0x00CED1FF,
        "medium turquoise": 0x48D1CCFF,
        "MediumTurquoise": 0x48D1CCFF,
        "turquoise": 0x40E0D0FF,
        "cyan": 0x00FFFFFF,
        "aqua": 0x00FFFFFF,
        "light cyan": 0xE0FFFFFF,
        "LightCyan": 0xE0FFFFFF,
        "cadet blue": 0x5F9EA0FF,
        "CadetBlue": 0x5F9EA0FF,
        "medium aquamarine": 0x66CDAAFF,
        "MediumAquamarine": 0x66CDAAFF,
        "aquamarine": 0x7FFFD4FF,
        "dark green": 0x006400FF,
        "DarkGreen": 0x006400FF,
        "dark olive green": 0x556B2FFF,
        "DarkOliveGreen": 0x556B2FFF,
        "dark sea green": 0x8FBC8FFF,
        "DarkSeaGreen": 0x8FBC8FFF,
        "sea green": 0x2E8B57FF,
        "SeaGreen": 0x2E8B57FF,
        "medium sea green": 0x3CB371FF,
        "MediumSeaGreen": 0x3CB371FF,
        "light sea green": 0x20B2AAFF,
        "LightSeaGreen": 0x20B2AAFF,
        "pale green": 0x98FB98FF,
        "PaleGreen": 0x98FB98FF,
        "spring green": 0x00FF7FFF,
        "SpringGreen": 0x00FF7FFF,
        "lawn green": 0x7CFC00FF,
        "LawnGreen": 0x7CFC00FF,
        "green": 0x00FF00FF,
        "lime": 0x00FF00FF,
        "x11 green": 0x00FF00FF,
        "X11Green": 0x00FF00FF,
        "web green": 0x008000FF,
        "WebGreen": 0x008000FF,
        "chartreuse": 0x7FFF00FF,
        "medium spring green": 0x00FA9AFF,
        "MediumSpringGreen": 0x00FA9AFF,
        "green yellow": 0xADFF2FFF,
        "GreenYellow": 0xADFF2FFF,
        "lime green": 0x32CD32FF,
        "LimeGreen": 0x32CD32FF,
        "yellow green": 0x9ACD32FF,
        "YellowGreen": 0x9ACD32FF,
        "forest green": 0x228B22FF,
        "ForestGreen": 0x228B22FF,
        "olive drab": 0x6B8E23FF,
        "OliveDrab": 0x6B8E23FF,
        "dark khaki": 0xBDB76BFF,
        "DarkKhaki": 0xBDB76BFF,
        "khaki": 0xF0E68CFF,
        "pale goldenrod": 0xEEE8AAFF,
        "PaleGoldenrod": 0xEEE8AAFF,
        "light goldenrod yellow": 0xFAFAD2FF,
        "LightGoldenrodYellow": 0xFAFAD2FF,
        "light yellow": 0xFFFFE0FF,
        "LightYellow": 0xFFFFE0FF,
        "yellow": 0xFFFF00FF,
        "gold": 0xFFD700FF,
        "light goldenrod": 0xEEDD82FF,
        "LightGoldenrod": 0xEEDD82FF,
        "goldenrod": 0xDAA520FF,
        "dark goldenrod": 0xB8860BFF,
        "DarkGoldenrod": 0xB8860BFF,
        "rosy brown": 0xBC8F8FFF,
        "RosyBrown": 0xBC8F8FFF,
        "indian red": 0xCD5C5CFF,
        "IndianRed": 0xCD5C5CFF,
        "saddle brown": 0x8B4513FF,
        "SaddleBrown": 0x8B4513FF,
        "sienna": 0xA0522DFF,
        "peru": 0xCD853FFF,
        "burlywood": 0xDEB887FF,
        "beige": 0xF5F5DCFF,
        "wheat": 0xF5DEB3FF,
        "sandy brown": 0xF4A460FF,
        "SandyBrown": 0xF4A460FF,
        "tan": 0xD2B48CFF,
        "chocolate": 0xD2691EFF,
        "firebrick": 0xB22222FF,
        "brown": 0xA52A2AFF,
        "dark salmon": 0xE9967AFF,
        "DarkSalmon": 0xE9967AFF,
        "salmon": 0xFA8072FF,
        "light salmon": 0xFFA07AFF,
        "LightSalmon": 0xFFA07AFF,
        "orange": 0xFFA500FF,
        "dark orange": 0xFF8C00FF,
        "DarkOrange": 0xFF8C00FF,
        "coral": 0xFF7F50FF,
        "light coral": 0xF08080FF,
        "LightCoral": 0xF08080FF,
        "tomato": 0xFF6347FF,
        "orange red": 0xFF4500FF,
        "OrangeRed": 0xFF4500FF,
        "red": 0xFF0000FF,
        "hot pink": 0xFF69B4FF,
        "HotPink": 0xFF69B4FF,
        "deep pink": 0xFF1493FF,
        "DeepPink": 0xFF1493FF,
        "pink": 0xFFC0CBFF,
        "light pink": 0xFFB6C1FF,
        "LightPink": 0xFFB6C1FF,
        "pale violet red": 0xDB7093FF,
        "PaleVioletRed": 0xDB7093FF,
        "maroon": 0xB03060FF,
        "x11 maroon": 0xB03060FF,
        "X11Maroon": 0xB03060FF,
        "web maroon": 0x800000FF,
        "WebMaroon": 0x800000FF,
        "medium violet red": 0xC71585FF,
        "MediumVioletRed": 0xC71585FF,
        "violet red": 0xD02090FF,
        "VioletRed": 0xD02090FF,
        "magenta": 0xFF00FFFF,
        "fuchsia": 0xFF00FFFF,
        "violet": 0xEE82EEFF,
        "plum": 0xDDA0DDFF,
        "orchid": 0xDA70D6FF,
        "medium orchid": 0xBA55D3FF,
        "MediumOrchid": 0xBA55D3FF,
        "dark orchid": 0x9932CCFF,
        "DarkOrchid": 0x9932CCFF,
        "dark violet": 0x9400D3FF,
        "DarkViolet": 0x9400D3FF,
        "blue violet": 0x8A2BE2FF,
        "BlueViolet": 0x8A2BE2FF,
        "purple": 0xA020F0FF,
        "x11 purple": 0xA020F0FF,
        "X11Purple": 0xA020F0FF,
        "web purple": 0x800080FF,
        "WebPurple": 0x800080FF,
        "medium purple": 0x9370DBFF,
        "MediumPurple": 0x9370DBFF,
        "thistle": 0xD8BFD8FF,
        "snow1": 0xFFFAFAFF,
        "snow2": 0xEEE9E9FF,
        "snow3": 0xCDC9C9FF,
        "snow4": 0x8B8989FF,
        "seashell1": 0xFFF5EEFF,
        "seashell2": 0xEEE5DEFF,
        "seashell3": 0xCDC5BFFF,
        "seashell4": 0x8B8682FF,
        "AntiqueWhite1": 0xFFEFDBFF,
        "AntiqueWhite2": 0xEEDFCCFF,
        "AntiqueWhite3": 0xCDC0B0FF,
        "AntiqueWhite4": 0x8B8378FF,
        "bisque1": 0xFFE4C4FF,
        "bisque2": 0xEED5B7FF,
        "bisque3": 0xCDB79EFF,
        "bisque4": 0x8B7D6BFF,
        "PeachPuff1": 0xFFDAB9FF,
        "PeachPuff2": 0xEECBADFF,
        "PeachPuff3": 0xCDAF95FF,
        "PeachPuff4": 0x8B7765FF,
        "NavajoWhite1": 0xFFDEADFF,
        "NavajoWhite2": 0xEECFA1FF,
        "NavajoWhite3": 0xCDB38BFF,
        "NavajoWhite4": 0x8B795EFF,
        "LemonChiffon1": 0xFFFACDFF,
        "LemonChiffon2": 0xEEE9BFFF,
        "LemonChiffon3": 0xCDC9A5FF,
        "LemonChiffon4": 0x8B8970FF,
        "cornsilk1": 0xFFF8DCFF,
        "cornsilk2": 0xEEE8CDFF,
        "cornsilk3": 0xCDC8B1FF,
        "cornsilk4": 0x8B8878FF,
        "ivory1": 0xFFFFF0FF,
        "ivory2": 0xEEEEE0FF,
        "ivory3": 0xCDCDC1FF,
        "ivory4": 0x8B8B83FF,
        "honeydew1": 0xF0FFF0FF,
        "honeydew2": 0xE0EEE0FF,
        "honeydew3": 0xC1CDC1FF,
        "honeydew4": 0x838B83FF,
        "LavenderBlush1": 0xFFF0F5FF,
        "LavenderBlush2": 0xEEE0E5FF,
        "LavenderBlush3": 0xCDC1C5FF,
        "LavenderBlush4": 0x8B8386FF,
        "MistyRose1": 0xFFE4E1FF,
        "MistyRose2": 0xEED5D2FF,
        "MistyRose3": 0xCDB7B5FF,
        "MistyRose4": 0x8B7D7BFF,
        "azure1": 0xF0FFFFFF,
        "azure2": 0xE0EEEEFF,
        "azure3": 0xC1CDCDFF,
        "azure4": 0x838B8BFF,
        "SlateBlue1": 0x836FFFFF,
        "SlateBlue2": 0x7A67EEFF,
        "SlateBlue3": 0x6959CDFF,
        "SlateBlue4": 0x473C8BFF,
        "RoyalBlue1": 0x4876FFFF,
        "RoyalBlue2": 0x436EEEFF,
        "RoyalBlue3": 0x3A5FCDFF,
        "RoyalBlue4": 0x27408BFF,
        "blue1": 0x0000FFFF,
        "blue2": 0x0000EEFF,
        "blue3": 0x0000CDFF,
        "blue4": 0x00008BFF,
        "DodgerBlue1": 0x1E90FFFF,
        "DodgerBlue2": 0x1C86EEFF,
        "DodgerBlue3": 0x1874CDFF,
        "DodgerBlue4": 0x104E8BFF,
        "SteelBlue1": 0x63B8FFFF,
        "SteelBlue2": 0x5CACEEFF,
        "SteelBlue3": 0x4F94CDFF,
        "SteelBlue4": 0x36648BFF,
        "DeepSkyBlue1": 0x00BFFFFF,
        "DeepSkyBlue2": 0x00B2EEFF,
        "DeepSkyBlue3": 0x009ACDFF,
        "DeepSkyBlue4": 0x00688BFF,
        "SkyBlue1": 0x87CEFFFF,
        "SkyBlue2": 0x7EC0EEFF,
        "SkyBlue3": 0x6CA6CDFF,
        "SkyBlue4": 0x4A708BFF,
        "LightSkyBlue1": 0xB0E2FFFF,
        "LightSkyBlue2": 0xA4D3EEFF,
        "LightSkyBlue3": 0x8DB6CDFF,
        "LightSkyBlue4": 0x607B8BFF,
        "SlateGray1": 0xC6E2FFFF,
        "SlateGray2": 0xB9D3EEFF,
        "SlateGray3": 0x9FB6CDFF,
        "SlateGray4": 0x6C7B8BFF,
        "LightSteelBlue1": 0xCAE1FFFF,
        "LightSteelBlue2": 0xBCD2EEFF,
        "LightSteelBlue3": 0xA2B5CDFF,
        "LightSteelBlue4": 0x6E7B8BFF,
        "LightBlue1": 0xBFEFFFFF,
        "LightBlue2": 0xB2DFEEFF,
        "LightBlue3": 0x9AC0CDFF,
        "LightBlue4": 0x68838BFF,
        "LightCyan1": 0xE0FFFFFF,
        "LightCyan2": 0xD1EEEEFF,
        "LightCyan3": 0xB4CDCDFF,
        "LightCyan4": 0x7A8B8BFF,
        "PaleTurquoise1": 0xBBFFFFFF,
        "PaleTurquoise2": 0xAEEEEEFF,
        "PaleTurquoise3": 0x96CDCDFF,
        "PaleTurquoise4": 0x668B8BFF,
        "CadetBlue1": 0x98F5FFFF,
        "CadetBlue2": 0x8EE5EEFF,
        "CadetBlue3": 0x7AC5CDFF,
        "CadetBlue4": 0x53868BFF,
        "turquoise1": 0x00F5FFFF,
        "turquoise2": 0x00E5EEFF,
        "turquoise3": 0x00C5CDFF,
        "turquoise4": 0x00868BFF,
        "cyan1": 0x00FFFFFF,
        "cyan2": 0x00EEEEFF,
        "cyan3": 0x00CDCDFF,
        "cyan4": 0x008B8BFF,
        "DarkSlateGray1": 0x97FFFFFF,
        "DarkSlateGray2": 0x8DEEEEFF,
        "DarkSlateGray3": 0x79CDCDFF,
        "DarkSlateGray4": 0x528B8BFF,
        "aquamarine1": 0x7FFFD4FF,
        "aquamarine2": 0x76EEC6FF,
        "aquamarine3": 0x66CDAAFF,
        "aquamarine4": 0x458B74FF,
        "DarkSeaGreen1": 0xC1FFC1FF,
        "DarkSeaGreen2": 0xB4EEB4FF,
        "DarkSeaGreen3": 0x9BCD9BFF,
        "DarkSeaGreen4": 0x698B69FF,
        "SeaGreen1": 0x54FF9FFF,
        "SeaGreen2": 0x4EEE94FF,
        "SeaGreen3": 0x43CD80FF,
        "SeaGreen4": 0x2E8B57FF,
        "PaleGreen1": 0x9AFF9AFF,
        "PaleGreen2": 0x90EE90FF,
        "PaleGreen3": 0x7CCD7CFF,
        "PaleGreen4": 0x548B54FF,
        "SpringGreen1": 0x00FF7FFF,
        "SpringGreen2": 0x00EE76FF,
        "SpringGreen3": 0x00CD66FF,
        "SpringGreen4": 0x008B45FF,
        "green1": 0x00FF00FF,
        "green2": 0x00EE00FF,
        "green3": 0x00CD00FF,
        "green4": 0x008B00FF,
        "chartreuse1": 0x7FFF00FF,
        "chartreuse2": 0x76EE00FF,
        "chartreuse3": 0x66CD00FF,
        "chartreuse4": 0x458B00FF,
        "OliveDrab1": 0xC0FF3EFF,
        "OliveDrab2": 0xB3EE3AFF,
        "OliveDrab3": 0x9ACD32FF,
        "OliveDrab4": 0x698B22FF,
        "DarkOliveGreen1": 0xCAFF70FF,
        "DarkOliveGreen2": 0xBCEE68FF,
        "DarkOliveGreen3": 0xA2CD5AFF,
        "DarkOliveGreen4": 0x6E8B3DFF,
        "khaki1": 0xFFF68FFF,
        "khaki2": 0xEEE685FF,
        "khaki3": 0xCDC673FF,
        "khaki4": 0x8B864EFF,
        "LightGoldenrod1": 0xFFEC8BFF,
        "LightGoldenrod2": 0xEEDC82FF,
        "LightGoldenrod3": 0xCDBE70FF,
        "LightGoldenrod4": 0x8B814CFF,
        "LightYellow1": 0xFFFFE0FF,
        "LightYellow2": 0xEEEED1FF,
        "LightYellow3": 0xCDCDB4FF,
        "LightYellow4": 0x8B8B7AFF,
        "yellow1": 0xFFFF00FF,
        "yellow2": 0xEEEE00FF,
        "yellow3": 0xCDCD00FF,
        "yellow4": 0x8B8B00FF,
        "gold1": 0xFFD700FF,
        "gold2": 0xEEC900FF,
        "gold3": 0xCDAD00FF,
        "gold4": 0x8B7500FF,
        "goldenrod1": 0xFFC125FF,
        "goldenrod2": 0xEEB422FF,
        "goldenrod3": 0xCD9B1DFF,
        "goldenrod4": 0x8B6914FF,
        "DarkGoldenrod1": 0xFFB90FFF,
        "DarkGoldenrod2": 0xEEAD0EFF,
        "DarkGoldenrod3": 0xCD950CFF,
        "DarkGoldenrod4": 0x8B6508FF,
        "RosyBrown1": 0xFFC1C1FF,
        "RosyBrown2": 0xEEB4B4FF,
        "RosyBrown3": 0xCD9B9BFF,
        "RosyBrown4": 0x8B6969FF,
        "IndianRed1": 0xFF6A6AFF,
        "IndianRed2": 0xEE6363FF,
        "IndianRed3": 0xCD5555FF,
        "IndianRed4": 0x8B3A3AFF,
        "sienna1": 0xFF8247FF,
        "sienna2": 0xEE7942FF,
        "sienna3": 0xCD6839FF,
        "sienna4": 0x8B4726FF,
        "burlywood1": 0xFFD39BFF,
        "burlywood2": 0xEEC591FF,
        "burlywood3": 0xCDAA7DFF,
        "burlywood4": 0x8B7355FF,
        "wheat1": 0xFFE7BAFF,
        "wheat2": 0xEED8AEFF,
        "wheat3": 0xCDBA96FF,
        "wheat4": 0x8B7E66FF,
        "tan1": 0xFFA54FFF,
        "tan2": 0xEE9A49FF,
        "tan3": 0xCD853FFF,
        "tan4": 0x8B5A2BFF,
        "chocolate1": 0xFF7F24FF,
        "chocolate2": 0xEE7621FF,
        "chocolate3": 0xCD661DFF,
        "chocolate4": 0x8B4513FF,
        "firebrick1": 0xFF3030FF,
        "firebrick2": 0xEE2C2CFF,
        "firebrick3": 0xCD2626FF,
        "firebrick4": 0x8B1A1AFF,
        "brown1": 0xFF4040FF,
        "brown2": 0xEE3B3BFF,
        "brown3": 0xCD3333FF,
        "brown4": 0x8B2323FF,
        "salmon1": 0xFF8C69FF,
        "salmon2": 0xEE8262FF,
        "salmon3": 0xCD7054FF,
        "salmon4": 0x8B4C39FF,
        "LightSalmon1": 0xFFA07AFF,
        "LightSalmon2": 0xEE9572FF,
        "LightSalmon3": 0xCD8162FF,
        "LightSalmon4": 0x8B5742FF,
        "orange1": 0xFFA500FF,
        "orange2": 0xEE9A00FF,
        "orange3": 0xCD8500FF,
        "orange4": 0x8B5A00FF,
        "DarkOrange1": 0xFF7F00FF,
        "DarkOrange2": 0xEE7600FF,
        "DarkOrange3": 0xCD6600FF,
        "DarkOrange4": 0x8B4500FF,
        "coral1": 0xFF7256FF,
        "coral2": 0xEE6A50FF,
        "coral3": 0xCD5B45FF,
        "coral4": 0x8B3E2FFF,
        "tomato1": 0xFF6347FF,
        "tomato2": 0xEE5C42FF,
        "tomato3": 0xCD4F39FF,
        "tomato4": 0x8B3626FF,
        "OrangeRed1": 0xFF4500FF,
        "OrangeRed2": 0xEE4000FF,
        "OrangeRed3": 0xCD3700FF,
        "OrangeRed4": 0x8B2500FF,
        "red1": 0xFF0000FF,
        "red2": 0xEE0000FF,
        "red3": 0xCD0000FF,
        "red4": 0x8B0000FF,
        "DeepPink1": 0xFF1493FF,
        "DeepPink2": 0xEE1289FF,
        "DeepPink3": 0xCD1076FF,
        "DeepPink4": 0x8B0A50FF,
        "HotPink1": 0xFF6EB4FF,
        "HotPink2": 0xEE6AA7FF,
        "HotPink3": 0xCD6090FF,
        "HotPink4": 0x8B3A62FF,
        "pink1": 0xFFB5C5FF,
        "pink2": 0xEEA9B8FF,
        "pink3": 0xCD919EFF,
        "pink4": 0x8B636CFF,
        "LightPink1": 0xFFAEB9FF,
        "LightPink2": 0xEEA2ADFF,
        "LightPink3": 0xCD8C95FF,
        "LightPink4": 0x8B5F65FF,
        "PaleVioletRed1": 0xFF82ABFF,
        "PaleVioletRed2": 0xEE799FFF,
        "PaleVioletRed3": 0xCD6889FF,
        "PaleVioletRed4": 0x8B475DFF,
        "maroon1": 0xFF34B3FF,
        "maroon2": 0xEE30A7FF,
        "maroon3": 0xCD2990FF,
        "maroon4": 0x8B1C62FF,
        "VioletRed1": 0xFF3E96FF,
        "VioletRed2": 0xEE3A8CFF,
        "VioletRed3": 0xCD3278FF,
        "VioletRed4": 0x8B2252FF,
        "magenta1": 0xFF00FFFF,
        "magenta2": 0xEE00EEFF,
        "magenta3": 0xCD00CDFF,
        "magenta4": 0x8B008BFF,
        "orchid1": 0xFF83FAFF,
        "orchid2": 0xEE7AE9FF,
        "orchid3": 0xCD69C9FF,
        "orchid4": 0x8B4789FF,
        "plum1": 0xFFBBFFFF,
        "plum2": 0xEEAEEEFF,
        "plum3": 0xCD96CDFF,
        "plum4": 0x8B668BFF,
        "MediumOrchid1": 0xE066FFFF,
        "MediumOrchid2": 0xD15FEEFF,
        "MediumOrchid3": 0xB452CDFF,
        "MediumOrchid4": 0x7A378BFF,
        "DarkOrchid1": 0xBF3EFFFF,
        "DarkOrchid2": 0xB23AEEFF,
        "DarkOrchid3": 0x9A32CDFF,
        "DarkOrchid4": 0x68228BFF,
        "purple1": 0x9B30FFFF,
        "purple2": 0x912CEEFF,
        "purple3": 0x7D26CDFF,
        "purple4": 0x551A8BFF,
        "MediumPurple1": 0xAB82FFFF,
        "MediumPurple2": 0x9F79EEFF,
        "MediumPurple3": 0x8968CDFF,
        "MediumPurple4": 0x5D478BFF,
        "thistle1": 0xFFE1FFFF,
        "thistle2": 0xEED2EEFF,
        "thistle3": 0xCDB5CDFF,
        "thistle4": 0x8B7B8BFF,
        "gray0": 0x000000FF,
        "grey0": 0x000000FF,
        "gray1": 0x030303FF,
        "grey1": 0x030303FF,
        "gray2": 0x050505FF,
        "grey2": 0x050505FF,
        "gray3": 0x080808FF,
        "grey3": 0x080808FF,
        "gray4": 0x0A0A0AFF,
        "grey4": 0x0A0A0AFF,
        "gray5": 0x0D0D0DFF,
        "grey5": 0x0D0D0DFF,
        "gray6": 0x0F0F0FFF,
        "grey6": 0x0F0F0FFF,
        "gray7": 0x121212FF,
        "grey7": 0x121212FF,
        "gray8": 0x141414FF,
        "grey8": 0x141414FF,
        "gray9": 0x171717FF,
        "grey9": 0x171717FF,
        "gray10": 0x1A1A1AFF,
        "grey10": 0x1A1A1AFF,
        "gray11": 0x1C1C1CFF,
        "grey11": 0x1C1C1CFF,
        "gray12": 0x1F1F1FFF,
        "grey12": 0x1F1F1FFF,
        "gray13": 0x212121FF,
        "grey13": 0x212121FF,
        "gray14": 0x242424FF,
        "grey14": 0x242424FF,
        "gray15": 0x262626FF,
        "grey15": 0x262626FF,
        "gray16": 0x292929FF,
        "grey16": 0x292929FF,
        "gray17": 0x2B2B2BFF,
        "grey17": 0x2B2B2BFF,
        "gray18": 0x2E2E2EFF,
        "grey18": 0x2E2E2EFF,
        "gray19": 0x303030FF,
        "grey19": 0x303030FF,
        "gray20": 0x333333FF,
        "grey20": 0x333333FF,
        "gray21": 0x363636FF,
        "grey21": 0x363636FF,
        "gray22": 0x383838FF,
        "grey22": 0x383838FF,
        "gray23": 0x3B3B3BFF,
        "grey23": 0x3B3B3BFF,
        "gray24": 0x3D3D3DFF,
        "grey24": 0x3D3D3DFF,
        "gray25": 0x404040FF,
        "grey25": 0x404040FF,
        "gray26": 0x424242FF,
        "grey26": 0x424242FF,
        "gray27": 0x454545FF,
        "grey27": 0x454545FF,
        "gray28": 0x474747FF,
        "grey28": 0x474747FF,
        "gray29": 0x4A4A4AFF,
        "grey29": 0x4A4A4AFF,
        "gray30": 0x4D4D4DFF,
        "grey30": 0x4D4D4DFF,
        "gray31": 0x4F4F4FFF,
        "grey31": 0x4F4F4FFF,
        "gray32": 0x525252FF,
        "grey32": 0x525252FF,
        "gray33": 0x545454FF,
        "grey33": 0x545454FF,
        "gray34": 0x575757FF,
        "grey34": 0x575757FF,
        "gray35": 0x595959FF,
        "grey35": 0x595959FF,
        "gray36": 0x5C5C5CFF,
        "grey36": 0x5C5C5CFF,
        "gray37": 0x5E5E5EFF,
        "grey37": 0x5E5E5EFF,
        "gray38": 0x616161FF,
        "grey38": 0x616161FF,
        "gray39": 0x636363FF,
        "grey39": 0x636363FF,
        "gray40": 0x666666FF,
        "grey40": 0x666666FF,
        "gray41": 0x696969FF,
        "grey41": 0x696969FF,
        "gray42": 0x6B6B6BFF,
        "grey42": 0x6B6B6BFF,
        "gray43": 0x6E6E6EFF,
        "grey43": 0x6E6E6EFF,
        "gray44": 0x707070FF,
        "grey44": 0x707070FF,
        "gray45": 0x737373FF,
        "grey45": 0x737373FF,
        "gray46": 0x757575FF,
        "grey46": 0x757575FF,
        "gray47": 0x787878FF,
        "grey47": 0x787878FF,
        "gray48": 0x7A7A7AFF,
        "grey48": 0x7A7A7AFF,
        "gray49": 0x7D7D7DFF,
        "grey49": 0x7D7D7DFF,
        "gray50": 0x7F7F7FFF,
        "grey50": 0x7F7F7FFF,
        "gray51": 0x828282FF,
        "grey51": 0x828282FF,
        "gray52": 0x858585FF,
        "grey52": 0x858585FF,
        "gray53": 0x878787FF,
        "grey53": 0x878787FF,
        "gray54": 0x8A8A8AFF,
        "grey54": 0x8A8A8AFF,
        "gray55": 0x8C8C8CFF,
        "grey55": 0x8C8C8CFF,
        "gray56": 0x8F8F8FFF,
        "grey56": 0x8F8F8FFF,
        "gray57": 0x919191FF,
        "grey57": 0x919191FF,
        "gray58": 0x949494FF,
        "grey58": 0x949494FF,
        "gray59": 0x969696FF,
        "grey59": 0x969696FF,
        "gray60": 0x999999FF,
        "grey60": 0x999999FF,
        "gray61": 0x9C9C9CFF,
        "grey61": 0x9C9C9CFF,
        "gray62": 0x9E9E9EFF,
        "grey62": 0x9E9E9EFF,
        "gray63": 0xA1A1A1FF,
        "grey63": 0xA1A1A1FF,
        "gray64": 0xA3A3A3FF,
        "grey64": 0xA3A3A3FF,
        "gray65": 0xA6A6A6FF,
        "grey65": 0xA6A6A6FF,
        "gray66": 0xA8A8A8FF,
        "grey66": 0xA8A8A8FF,
        "gray67": 0xABABABFF,
        "grey67": 0xABABABFF,
        "gray68": 0xADADADFF,
        "grey68": 0xADADADFF,
        "gray69": 0xB0B0B0FF,
        "grey69": 0xB0B0B0FF,
        "gray70": 0xB3B3B3FF,
        "grey70": 0xB3B3B3FF,
        "gray71": 0xB5B5B5FF,
        "grey71": 0xB5B5B5FF,
        "gray72": 0xB8B8B8FF,
        "grey72": 0xB8B8B8FF,
        "gray73": 0xBABABAFF,
        "grey73": 0xBABABAFF,
        "gray74": 0xBDBDBDFF,
        "grey74": 0xBDBDBDFF,
        "gray75": 0xBFBFBFFF,
        "grey75": 0xBFBFBFFF,
        "gray76": 0xC2C2C2FF,
        "grey76": 0xC2C2C2FF,
        "gray77": 0xC4C4C4FF,
        "grey77": 0xC4C4C4FF,
        "gray78": 0xC7C7C7FF,
        "grey78": 0xC7C7C7FF,
        "gray79": 0xC9C9C9FF,
        "grey79": 0xC9C9C9FF,
        "gray80": 0xCCCCCCFF,
        "grey80": 0xCCCCCCFF,
        "gray81": 0xCFCFCFFF,
        "grey81": 0xCFCFCFFF,
        "gray82": 0xD1D1D1FF,
        "grey82": 0xD1D1D1FF,
        "gray83": 0xD4D4D4FF,
        "grey83": 0xD4D4D4FF,
        "gray84": 0xD6D6D6FF,
        "grey84": 0xD6D6D6FF,
        "gray85": 0xD9D9D9FF,
        "grey85": 0xD9D9D9FF,
        "gray86": 0xDBDBDBFF,
        "grey86": 0xDBDBDBFF,
        "gray87": 0xDEDEDEFF,
        "grey87": 0xDEDEDEFF,
        "gray88": 0xE0E0E0FF,
        "grey88": 0xE0E0E0FF,
        "gray89": 0xE3E3E3FF,
        "grey89": 0xE3E3E3FF,
        "gray90": 0xE5E5E5FF,
        "grey90": 0xE5E5E5FF,
        "gray91": 0xE8E8E8FF,
        "grey91": 0xE8E8E8FF,
        "gray92": 0xEBEBEBFF,
        "grey92": 0xEBEBEBFF,
        "gray93": 0xEDEDEDFF,
        "grey93": 0xEDEDEDFF,
        "gray94": 0xF0F0F0FF,
        "grey94": 0xF0F0F0FF,
        "gray95": 0xF2F2F2FF,
        "grey95": 0xF2F2F2FF,
        "gray96": 0xF5F5F5FF,
        "grey96": 0xF5F5F5FF,
        "gray97": 0xF7F7F7FF,
        "grey97": 0xF7F7F7FF,
        "gray98": 0xFAFAFAFF,
        "grey98": 0xFAFAFAFF,
        "gray99": 0xFCFCFCFF,
        "grey99": 0xFCFCFCFF,
        "gray100": 0xFFFFFFFF,
        "grey100": 0xFFFFFFFF,
        "dark grey": 0xA9A9A9FF,
        "DarkGrey": 0xA9A9A9FF,
        "dark gray": 0xA9A9A9FF,
        "DarkGray": 0xA9A9A9FF,
        "dark blue": 0x00008BFF,
        "DarkBlue": 0x00008BFF,
        "dark cyan": 0x008B8BFF,
        "DarkCyan": 0x008B8BFF,
        "dark magenta": 0x8B008BFF,
        "DarkMagenta": 0x8B008BFF,
        "dark red": 0x8B0000FF,
        "DarkRed": 0x8B0000FF,
        "light green": 0x90EE90FF,
        "LightGreen": 0x90EE90FF,
        "crimson": 0xDC143CFF,
        "indigo": 0x4B0082FF,
        "olive": 0x808000FF,
        "rebecca purple": 0x663399FF,
        "RebeccaPurple": 0x663399FF,
        "silver": 0xC0C0C0FF,
        "teal": 0x008080FF,
    }
    X11_NAMES_INVERSE: Final[Mapping[int, str]] = {
        _v: _k for _k, _v in X11_NAMES.items()
    }
    X11_NAMES_COLLATED: Final[Mapping[str, int]] = {
        remove_ascii_spaces(_k).casefold(): _v for _k, _v in X11_NAMES.items()
    }
