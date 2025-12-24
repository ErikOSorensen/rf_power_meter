# Power Display Module
# Renders power readings on SSD1306 OLED displays

from .ssd1306 import SSD1306_I2C
import config

# Large digit font (16x24 pixels) - simplified bitmap representation
# Each digit is represented as a list of horizontal lines
LARGE_DIGITS = {
    '0': [(2, 12), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (2, 12)],
    '1': [(6, 8), (4, 10), (6, 8), (6, 8), (6, 8), (6, 8), (4, 12)],
    '2': [(2, 12), (0, 14), (10, 14), (6, 10), (2, 6), (0, 4), (0, 14)],
    '3': [(2, 12), (0, 14), (10, 14), (6, 12), (10, 14), (0, 14), (2, 12)],
    '4': [(0, 4), (0, 4), (0, 10), (0, 14), (10, 14), (10, 14), (10, 14)],
    '5': [(0, 14), (0, 4), (0, 12), (10, 14), (10, 14), (0, 14), (2, 12)],
    '6': [(4, 12), (2, 6), (0, 4), (0, 12), (0, 14), (0, 14), (2, 12)],
    '7': [(0, 14), (10, 14), (8, 12), (6, 10), (4, 8), (4, 8), (4, 8)],
    '8': [(2, 12), (0, 14), (0, 14), (2, 12), (0, 14), (0, 14), (2, 12)],
    '9': [(2, 12), (0, 14), (0, 14), (2, 14), (10, 14), (8, 12), (2, 10)],
    '-': [(0, 0), (0, 0), (0, 0), (2, 12), (0, 0), (0, 0), (0, 0)],
    '.': [(0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (5, 9)],
    ' ': [(0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)],
}


class PowerDisplay:
    """Display power reading on OLED."""

    def __init__(self, i2c, address, channel_num):
        """
        Initialize power display.

        Args:
            i2c: I2C bus instance
            address: OLED I2C address
            channel_num: Channel number for labeling
        """
        self.display = SSD1306_I2C(
            config.DISPLAY_WIDTH,
            config.DISPLAY_HEIGHT,
            i2c,
            address
        )
        self.channel_num = channel_num
        self.last_power = None
        self.last_unit = None
        self.last_sensor = None

    def clear(self):
        """Clear display."""
        self.display.fill(0)

    def show(self):
        """Update display."""
        self.display.show()

    def draw_large_number(self, value, x, y, width=80):
        """
        Draw a large number for power reading.

        Args:
            value: Numeric value to display
            x: X position
            y: Y position
            width: Available width
        """
        if value is None:
            text = "---.-"
        else:
            # Format to one decimal place
            if value >= 0:
                text = "{:5.1f}".format(value)
            else:
                text = "{:5.1f}".format(value)

        # Use built-in font at 2x scale (simulated with filled rectangles)
        # Each character is 8 pixels wide in standard font
        char_width = 12
        char_height = 16

        for i, char in enumerate(text.strip()):
            cx = x + i * char_width
            # Draw character using 2x2 pixel blocks
            self._draw_char_large(char, cx, y, 2)

    def _draw_char_large(self, char, x, y, scale=2):
        """Draw a character at larger scale."""
        # Use standard 8x8 font, scaled up
        self.display.text(char, x, y, 1)
        # For larger text, we draw multiple times offset
        if scale >= 2:
            self.display.text(char, x + 1, y, 1)
            self.display.text(char, x, y + 1, 1)
            self.display.text(char, x + 1, y + 1, 1)

    def draw_power_bar(self, power_dbm, y, min_dbm=-60, max_dbm=10):
        """
        Draw power level bar graph.

        Args:
            power_dbm: Power in dBm
            y: Y position
            min_dbm: Minimum scale value
            max_dbm: Maximum scale value
        """
        bar_width = config.DISPLAY_WIDTH - 4
        bar_height = 8

        # Draw outline
        self.display.rect(2, y, bar_width, bar_height, 1)

        if power_dbm is not None:
            # Calculate fill level
            level = (power_dbm - min_dbm) / (max_dbm - min_dbm)
            level = max(0.0, min(1.0, level))
            fill_width = int((bar_width - 2) * level)

            if fill_width > 0:
                self.display.fill_rect(3, y + 1, fill_width, bar_height - 2, 1)

    def update(self, power_value, unit_str, sensor_type=None, ip_addr=None, attenuator=0.0):
        """
        Update display with new reading.

        Args:
            power_value: Power value (or None for no sensor)
            unit_str: Unit string (dBm, mW, etc.)
            sensor_type: Detected sensor type
            ip_addr: IP address to show
            attenuator: External attenuator value in dB (0 = none)
        """
        self.clear()

        # Channel label (top left)
        self.display.text("CH{}".format(self.channel_num), 0, 0, 1)

        # Attenuator indicator (next to channel) if active
        if attenuator != 0.0:
            atten_str = "+{:.0f}dB".format(attenuator)
            self.display.text(atten_str, 28, 0, 1)

        # Sensor type (top right)
        if sensor_type:
            sensor_text = sensor_type[:8]  # Truncate if needed
            x = config.DISPLAY_WIDTH - len(sensor_text) * 8
            self.display.text(sensor_text, x, 0, 1)
        else:
            self.display.text("NO SENSOR", 40, 0, 1)

        # Main power reading (large, centered)
        if power_value is not None:
            # Format power value
            if abs(power_value) >= 100:
                power_str = "{:.0f}".format(power_value)
            elif abs(power_value) >= 10:
                power_str = "{:.1f}".format(power_value)
            else:
                power_str = "{:.2f}".format(power_value)

            # Draw large power value
            self._draw_large_text(power_str, 4, 16)

            # Unit
            self.display.text(unit_str, 90, 24, 1)

            # Power bar
            self.draw_power_bar(power_value if unit_str == "dBm" else None, 44)
        else:
            # No sensor connected
            self._draw_large_text("----", 20, 16)
            self.display.text("NO SENSOR", 24, 40, 1)

        # IP address or status (bottom)
        if ip_addr:
            ip_text = ip_addr[:16]  # Truncate if needed
            self.display.text(ip_text, 0, 56, 1)
        else:
            self.display.text("DHCP...", 0, 56, 1)

        self.show()

        # Cache values
        self.last_power = power_value
        self.last_unit = unit_str
        self.last_sensor = sensor_type

    def _draw_large_text(self, text, x, y):
        """Draw text at 2x scale."""
        for i, char in enumerate(text):
            cx = x + i * 14  # 14 pixels per character at 2x
            # Draw each character 4 times for 2x effect
            self.display.text(char, cx, y, 1)
            self.display.text(char, cx + 1, y, 1)
            self.display.text(char, cx, y + 8, 1)
            self.display.text(char, cx + 1, y + 8, 1)
            # Fill in for bolder text
            self.display.text(char, cx, y + 1, 1)
            self.display.text(char, cx + 1, y + 1, 1)

    def show_startup(self):
        """Show startup screen."""
        self.clear()
        self.display.text("RF Power Meter", 8, 8, 1)
        self.display.text("Channel {}".format(self.channel_num), 32, 24, 1)
        self.display.text(config.MODEL, 40, 40, 1)
        self.display.text("v" + config.VERSION, 44, 52, 1)
        self.show()

    def show_error(self, message):
        """Show error message."""
        self.clear()
        self.display.text("ERROR", 44, 16, 1)
        # Word wrap message
        words = message.split()
        line = ""
        y = 32
        for word in words:
            if len(line) + len(word) + 1 <= 16:
                line += (" " if line else "") + word
            else:
                self.display.text(line, 0, y, 1)
                y += 10
                line = word
        if line:
            self.display.text(line, 0, y, 1)
        self.show()


class DisplayManager:
    """Manages both channel displays."""

    def __init__(self, i2c):
        """
        Initialize display manager.

        Args:
            i2c: I2C bus instance
        """
        self.displays = {
            1: PowerDisplay(i2c, config.OLED_ADDR_CH1, 1),
            2: PowerDisplay(i2c, config.OLED_ADDR_CH2, 2),
        }
        self.ip_address = None

    def set_ip_address(self, ip):
        """Set IP address to display."""
        self.ip_address = ip

    def show_startup(self):
        """Show startup screen on all displays."""
        for display in self.displays.values():
            display.show_startup()

    def update(self, channel_num, power_value, unit_str, sensor_type=None, attenuator=0.0):
        """Update specific channel display."""
        if channel_num in self.displays:
            self.displays[channel_num].update(
                power_value, unit_str, sensor_type, self.ip_address, attenuator
            )

    def update_all(self, meter):
        """
        Update all displays from power meter.

        Args:
            meter: PowerMeter instance
        """
        for ch_num, display in self.displays.items():
            channel = meter.get_channel(ch_num)
            if channel:
                power, unit = channel.get_power()
                display.update(
                    power, unit, channel.sensor_type,
                    self.ip_address, channel.get_attenuator()
                )

    def show_error(self, message):
        """Show error on all displays."""
        for display in self.displays.values():
            display.show_error(message)
