# Power Display Module
# Owns the SSD1322 panel and renders the meter state with display/layout.py

from machine import SPI, Pin
import time

from .ssd1322 import SSD1322
from . import layout
import config

NET_INFO_MS = 3000    # How long the IP address stays up once DHCP succeeds


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
        self.ip_address = None
        self._hold_until = None   # ticks_ms until which the startup screen stays

    def set_ip_address(self, ip):
        """
        Set the IP address. The startup screen shows it (or "Waiting for
        DHCP...") and, once an address arrives, stays up for NET_INFO_MS
        before the measurement screen takes over.
        """
        self.ip_address = ip
        layout.draw_startup(self.display, ip)
        self.display.show()
        if ip:
            self._hold_until = time.ticks_add(time.ticks_ms(), NET_INFO_MS)

    def show_startup(self):
        """Show startup screen."""
        layout.draw_startup(self.display, self.ip_address)
        self.display.show()

    def update_all(self, meter, edit=None, locked=False):
        """
        Redraw the whole panel from the power meter state.

        Args:
            meter: PowerMeter instance
            edit: (channel, field) being edited from the front panel, or None
            locked: True to show the remote-lock indicator
        """
        if self._hold_until is not None:
            if edit is None and time.ticks_diff(self._hold_until, time.ticks_ms()) > 0:
                return
            self._hold_until = None

        d = self.display
        d.fill(0)
        for ch_num in (1, 2):
            channel = meter.get_channel(ch_num)
            if channel is None:
                continue
            power, unit = channel.get_power()
            edit_field = edit[1] if edit and edit[0] == ch_num else None
            layout.draw_channel(
                d, (ch_num - 1) * layout.ROW_H, ch_num, power, unit,
                channel.sensor_type, channel.temperature,
                channel.get_frequency(), channel.get_attenuator(), edit_field)
        if locked:
            layout.draw_lock(d)
        d.show()

    def show_error(self, message):
        """Show an error message across the panel."""
        layout.draw_error(self.display, message)
        self.display.show()
