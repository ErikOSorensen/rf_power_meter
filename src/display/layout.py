# Screen layout for the 256x64 SSD1322 panel
#
# Pure drawing code: no hardware access, so it also runs on the desktop
# (see tests/test_screen.py). Every function draws into a target with
# framebuf-style fill/fill_rect/blit, such as display.ssd1322.SSD1322 or a
# framebuf.FrameBuffer.
#
# One 32 px row per channel. The reading, the unit and the info line share
# a baseline; the channel name sits just above the info line:
#
#   CH1 AD8307 23.4°C                -23.43
#   137 MHz, 20 dB pad                     dBm
#   ---------------- baseline ------------------
#
# The reading is right-aligned at a fixed x and the digits are tabular, so
# digits do not move as the value changes. The unit is left-aligned just
# after it. The frequency and pad fields can be edited from the front
# panel; the active field is drawn inverted.

from .bitmapfont import BitmapFont
from .fonts import b612_bold_30, b612_regular_12, b612_regular_9
import config

# Gray levels
BRIGHT = 15
LABEL = 10
DIM = 5

big = BitmapFont(b612_bold_30)
medium = BitmapFont(b612_regular_12)
small = BitmapFont(b612_regular_9)

# Geometry
WIDTH = config.DISPLAY_WIDTH
HEIGHT = config.DISPLAY_HEIGHT
ROW_H = 32            # One row per channel
PAD = 2               # Left/right margin
BASELINE = 29         # Common baseline, from the top of each row
SMALL_CAP = 7         # Cap height of the 9 px font
NAME_GAP = 2          # Blank rows between the channel name and the info line
UNIT_GAP = 4          # Space between the reading and the unit
TAG_GAP = 6           # Space between the channel name and the sensor tag
UNITS = ("dBm", "dBW", "mW", "W")

# Right edge of the reading: leaves room for the widest unit
READING_RIGHT = WIDTH - PAD - max(small.width(u) for u in UNITS) - UNIT_GAP


def format_power(value):
    """Format a power value: two decimals below 100, whole numbers above."""
    if value is None:
        return "----"
    if abs(value) >= 100:
        return "{:.0f}".format(value)
    return "{:.2f}".format(value)


def _field(target, font, s, x, y, highlight, col=LABEL):
    """Draw text; inverted (bright box, dark text) when highlighted."""
    if highlight:
        target.fill_rect(x - 1, y, font.width(s) + 2, font.height, BRIGHT)
        return font.text(target, s, x, y, 0, bg=BRIGHT)
    return font.text(target, s, x, y, col)


def draw_channel(target, top, channel_num, reading, unit, sensor_type=None,
                 temperature=None, frequency=None, attenuator=0.0,
                 edit_field=None):
    """
    Draw one channel row with its top at y = top.

    Args:
        reading:     power value in `unit`, or None for no reading
        unit:        "dBm", "dBW", "mW" or "W"
        sensor_type: head type string, or None if no head is connected
        temperature: head temperature in C, or None
        frequency:   frequency in MHz, or None if the head has none
        attenuator:  external pad in dB
        edit_field:  None, "freq" or "atten": field being edited
    """
    base = top + BASELINE
    small_y = base - small.baseline

    # Channel name, then sensor type and head temperature
    name_base = base - SMALL_CAP - NAME_GAP
    x = medium.text(target, "CH{}".format(channel_num), PAD,
                    name_base - medium.baseline, BRIGHT)
    if sensor_type:
        tag = sensor_type[:8]
        if temperature is not None:
            tag += " {:.1f}°C".format(temperature)
        small.text(target, tag, x + TAG_GAP, name_base - small.baseline, DIM)
    else:
        small.text(target, "NO SENSOR", x + TAG_GAP, name_base - small.baseline, DIM)

    # Info line: frequency and external pad
    x = PAD
    if frequency is not None:
        x = _field(target, small, "{:g} MHz".format(frequency), x, small_y,
                   edit_field == "freq")
        x = small.text(target, ", ", x, small_y, LABEL)
    _field(target, small, "{:g} dB pad".format(attenuator), x, small_y,
           edit_field == "atten")

    # Reading and unit
    if reading is None:
        big.text_right(target, "----", READING_RIGHT, base - big.baseline, DIM)
    else:
        big.text_right(target, format_power(reading), READING_RIGHT,
                       base - big.baseline, BRIGHT)
        small.text(target, unit, READING_RIGHT + UNIT_GAP, small_y, LABEL)


def draw_lock(target):
    """Remote-lock indicator, top right corner above the units."""
    small.text_right(target, "RMT", WIDTH - PAD, 0, LABEL)


def draw_startup(target, ip=None):
    """Startup screen: identity, then IP address and mDNS name."""
    target.fill(0)
    medium.text(target, "RF Power Meter", PAD, 0, BRIGHT)
    small.text(target, "{} v{}  SCPI port {}".format(
        config.MODEL, config.VERSION, config.SCPI_PORT), PAD, 17, DIM)
    if ip:
        medium.text(target, ip, PAD, 33, BRIGHT)
    else:
        medium.text(target, "Waiting for DHCP...", PAD, 33, DIM)
    small.text(target, config.MDNS_HOSTNAME + ".local", PAD, 50, LABEL)


def draw_error(target, message):
    """Error screen with the message word-wrapped to the panel width."""
    target.fill(0)
    medium.text(target, "ERROR", PAD, 0, BRIGHT)
    y = 18
    line = ""
    for word in message.split():
        trial = (line + " " + word) if line else word
        if line and small.width(trial) > WIDTH - 2 * PAD:
            small.text(target, line, PAD, y, LABEL)
            y += small.height
            line = word
        else:
            line = trial
    if line:
        small.text(target, line, PAD, y, LABEL)
