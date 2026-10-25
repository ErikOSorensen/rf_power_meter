# Power Display Module
# Renders both channels on one 256x64 SSD1322 grayscale OLED
#
# Layout (x grows right, y grows down):
#
#   0 ┌──────────────────────────────┬──────────────────────────────┐
#     │ CH1 23.4C         AD8307     │ CH2               NO SENSOR  │
#  10 │ ▐▀▌▐▀▌  ▐▀▌  (3x digits)     │  ----                        │
#  36 │ dBm ▐██████████░░░░░░░░░░▌   │                              │
#  46 │ 433MHz             [+40dB]   │                     +0dB     │
#  56 │ 192.168.1.100                          rfmeter.local        │
#     └──────────────────────────────┴──────────────────────────────┘
#
# The frequency and attenuator fields on the info line can be edited
# from the front panel encoder; the active field is drawn inverted.
#
# Gray levels: 15 = reading, 10 = labels, 5 = secondary text/outlines.

from machine import SPI, Pin
import framebuf

from .ssd1322 import SSD1322
import config

# Gray levels
BRIGHT = 15
LABEL = 10
DIM = 5

# Geometry
HALF_WIDTH = config.DISPLAY_WIDTH // 2
PANE_PAD = 2               # Left/right padding inside a pane
CHAR_W = 8                 # Built-in framebuf font
BIG_SCALE = 3              # Main reading at 3x -> 24 px tall
BIG_CHAR_W = CHAR_W * BIG_SCALE

Y_HEADER = 0
Y_READING = 10
Y_UNIT = 36
Y_INFO = 46
Y_STATUS = 56


class ScaledText:
    """Draws the 8x8 framebuf font at an integer scale."""

    def __init__(self):
        self._buf = bytearray(CHAR_W * CHAR_W // 2)
        self._fb = framebuf.FrameBuffer(self._buf, CHAR_W, CHAR_W, framebuf.GS4_HMSB)

    def draw(self, target, text, x, y, scale, col):
        """
        Draw text onto target (anything with fill_rect) at an integer scale.

        Returns the x position after the last character.
        """
        fb = self._fb
        for ch in text:
            fb.fill(0)
            fb.text(ch, 0, 0, 1)
            for row in range(CHAR_W):
                run_start = None
                for colx in range(CHAR_W + 1):
                    on = colx < CHAR_W and fb.pixel(colx, row)
                    if on and run_start is None:
                        run_start = colx
                    elif not on and run_start is not None:
                        target.fill_rect(
                            x + run_start * scale, y + row * scale,
                            (colx - run_start) * scale, scale, col)
                        run_start = None
            x += CHAR_W * scale
        return x


def format_power(value):
    """Format a power value into at most 5 characters."""
    if value is None:
        return "----"
    mag = abs(value)
    if mag >= 1000:
        return "{:.0f}".format(value)
    if mag >= 100:
        return "{:.0f}".format(value)
    if mag >= 10:
        return "{:.1f}".format(value)
    return "{:.2f}".format(value)


class ChannelPane:
    """One half of the display, showing a single channel."""

    def __init__(self, display, scaler, channel_num, x0):
        self.display = display
        self.scaler = scaler
        self.channel_num = channel_num
        self.x0 = x0                       # Left edge of this pane
        self.x1 = x0 + HALF_WIDTH - 1      # Right edge (inclusive)

    def _text(self, s, x, y, col=LABEL):
        self.display.text(s, self.x0 + x, y, col)

    def _text_right(self, s, y, col=LABEL):
        x = HALF_WIDTH - PANE_PAD - len(s) * CHAR_W
        self.display.text(s, self.x0 + x, y, col)

    def _field(self, s, x, y, highlight, col=LABEL):
        """Draw an editable field; inverted (bright box, dark text) when active."""
        if highlight:
            self.display.fill_rect(self.x0 + x - 1, y - 1, len(s) * CHAR_W + 1, CHAR_W + 2, BRIGHT)
            self.display.text(s, self.x0 + x, y, 0)
        else:
            self.display.text(s, self.x0 + x, y, col)

    def draw_power_bar(self, power_dbm, x, y, width, height=8,
                       min_dbm=-60, max_dbm=10):
        """Draw a bar graph of power level."""
        d = self.display
        d.rect(self.x0 + x, y, width, height, DIM)
        if power_dbm is None:
            return
        level = (power_dbm - min_dbm) / (max_dbm - min_dbm)
        level = max(0.0, min(1.0, level))
        fill = int((width - 2) * level)
        if fill > 0:
            d.fill_rect(self.x0 + x + 1, y + 1, fill, height - 2, BRIGHT)

    def update(self, power_value, unit_str, sensor_type=None,
               temperature=None, attenuator=0.0, frequency=None,
               edit_field=None):
        """
        Render this channel's pane into the frame buffer (no show).

        Args:
            edit_field: None, "freq" or "atten": which field is being
                        edited from the front panel (drawn inverted)
        """
        # Header: channel, head temperature, sensor type
        self._text("CH{}".format(self.channel_num), PANE_PAD, Y_HEADER, BRIGHT)
        if temperature is not None:
            self._text("{:.1f}C".format(temperature), PANE_PAD + 4 * CHAR_W, Y_HEADER, DIM)
        if sensor_type:
            self._text_right(sensor_type[:6], Y_HEADER, LABEL)
        else:
            self._text_right("NO SENSOR", Y_HEADER, DIM)

        # Main reading
        if power_value is not None:
            text = format_power(power_value)
            # Right-align the number inside the pane
            x = HALF_WIDTH - PANE_PAD - len(text) * BIG_CHAR_W
            self.scaler.draw(self.display, text, self.x0 + x, Y_READING, BIG_SCALE, BRIGHT)

            self._text(unit_str, PANE_PAD, Y_UNIT, LABEL)
            bar_x = PANE_PAD + 4 * CHAR_W
            self.draw_power_bar(power_value if unit_str == "dBm" else None,
                                bar_x, Y_UNIT, HALF_WIDTH - PANE_PAD - bar_x)
        else:
            x = HALF_WIDTH - PANE_PAD - 4 * BIG_CHAR_W
            self.scaler.draw(self.display, "----", self.x0 + x, Y_READING, BIG_SCALE, DIM)

        # Info line: frequency (left) and external attenuator (right)
        if frequency is not None:
            self._field("{:g}MHz".format(frequency), PANE_PAD, Y_INFO,
                        edit_field == "freq")
        atten_str = "{:+.0f}dB".format(attenuator)
        self._field(atten_str, HALF_WIDTH - PANE_PAD - len(atten_str) * CHAR_W, Y_INFO,
                    edit_field == "atten")


class DisplayManager:
    """Owns the single SSD1322 panel and renders both channels on it."""

    def __init__(self, spi=None):
        """
        Initialize the display.

        Args:
            spi: machine.SPI instance for the display, or None to create
                 SPI1 from the pins in config.py
        """
        if spi is None:
            spi = SPI(
                config.DISPLAY_SPI_ID,
                baudrate=config.DISPLAY_SPI_BAUD,
                polarity=0, phase=0,
                sck=Pin(config.DISPLAY_SCK),
                mosi=Pin(config.DISPLAY_MOSI),
            )
        self.display = SSD1322(
            spi,
            cs=Pin(config.DISPLAY_CS),
            dc=Pin(config.DISPLAY_DC),
            rst=Pin(config.DISPLAY_RST),
            width=config.DISPLAY_WIDTH,
            height=config.DISPLAY_HEIGHT,
            col_offset=config.DISPLAY_COL_OFFSET,
            contrast=config.DISPLAY_CONTRAST,
        )
        self.scaler = ScaledText()
        self.panes = {
            1: ChannelPane(self.display, self.scaler, 1, 0),
            2: ChannelPane(self.display, self.scaler, 2, HALF_WIDTH),
        }
        self.ip_address = None

    def set_ip_address(self, ip):
        """Set IP address to show on the status line."""
        self.ip_address = ip

    def _draw_status_line(self, locked=False):
        d = self.display
        if self.ip_address:
            d.text(self.ip_address[:15], PANE_PAD, Y_STATUS, LABEL)
        else:
            d.text("DHCP...", PANE_PAD, Y_STATUS, DIM)
        # Right side: hostname, or the remote-lock indicator
        right = "REMOTE LOCK" if locked else config.MDNS_HOSTNAME + ".local"
        d.text(right, config.DISPLAY_WIDTH - PANE_PAD - len(right) * CHAR_W, Y_STATUS,
               LABEL if locked else DIM)

    def _draw_divider(self):
        self.display.vline(HALF_WIDTH - 1, 0, Y_STATUS - 2, DIM)

    def show_startup(self):
        """Show startup screen."""
        d = self.display
        d.fill(0)
        self.scaler.draw(d, "RF Power Meter", 16, 8, 2, BRIGHT)
        d.text("{} v{}".format(config.MODEL, config.VERSION), 16, 32, LABEL)
        d.text("Dual channel, SCPI port {}".format(config.SCPI_PORT), 16, 44, DIM)
        d.show()

    def update_all(self, meter, edit=None, locked=False):
        """
        Redraw the whole panel from the power meter state.

        Args:
            meter: PowerMeter instance
            edit: (channel, field) being edited from the front panel, or None
            locked: True to show the remote-lock indicator
        """
        d = self.display
        d.fill(0)
        for ch_num, pane in self.panes.items():
            channel = meter.get_channel(ch_num)
            if channel is None:
                continue
            power, unit = channel.get_power()
            edit_field = edit[1] if edit and edit[0] == ch_num else None
            pane.update(power, unit, channel.sensor_type,
                        channel.temperature, channel.get_attenuator(),
                        channel.get_frequency(), edit_field)
        self._draw_divider()
        self._draw_status_line(locked)
        d.show()

    def show_error(self, message):
        """Show an error message across the panel."""
        d = self.display
        d.fill(0)
        self.scaler.draw(d, "ERROR", 8, 8, 2, BRIGHT)
        # Word wrap at 30 characters
        words = message.split()
        line = ""
        y = 32
        for word in words:
            if len(line) + len(word) + 1 <= 30:
                line += (" " if line else "") + word
            else:
                d.text(line, 8, y, LABEL)
                y += 10
                line = word
        if line:
            d.text(line, 8, y, LABEL)
        d.show()
