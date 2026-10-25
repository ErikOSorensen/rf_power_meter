# SSD1322 OLED Driver for MicroPython
# 256x64 4-bit grayscale panel, 4-wire SPI (SCK, MOSI, CS, DC, RST)
#
# The frame buffer uses framebuf.GS4_HMSB: two pixels per byte with the
# left pixel in the high nibble. That is exactly the SSD1322's RAM layout,
# so show() streams the buffer straight out without any repacking.

from micropython import const
import framebuf
import time

# Commands
_ENABLE_GRAYSCALE_TABLE = const(0x00)
_SET_COLUMN_ADDR = const(0x15)
_WRITE_RAM = const(0x5C)
_SET_ROW_ADDR = const(0x75)
_SET_REMAP = const(0xA0)
_SET_START_LINE = const(0xA1)
_SET_DISPLAY_OFFSET = const(0xA2)
_SET_DISPLAY_ALL_OFF = const(0xA4)
_SET_DISPLAY_ALL_ON = const(0xA5)
_SET_DISPLAY_NORMAL = const(0xA6)
_SET_DISPLAY_INVERSE = const(0xA7)
_EXIT_PARTIAL = const(0xA9)
_SET_FUNCTION_SELECT = const(0xAB)
_DISPLAY_OFF = const(0xAE)
_DISPLAY_ON = const(0xAF)
_SET_PHASE_LENGTH = const(0xB1)
_SET_CLOCK_DIV = const(0xB3)
_SET_ENHANCEMENT_A = const(0xB4)
_SET_GPIO = const(0xB5)
_SET_SECOND_PRECHARGE = const(0xB6)
_DEFAULT_GRAYSCALE = const(0xB9)
_SET_PRECHARGE_VOLTAGE = const(0xBB)
_SET_VCOMH = const(0xBE)
_SET_CONTRAST = const(0xC1)
_SET_MASTER_CONTRAST = const(0xC7)
_SET_MUX_RATIO = const(0xCA)
_SET_ENHANCEMENT_B = const(0xD1)
_SET_COMMAND_LOCK = const(0xFD)


class SSD1322:
    """
    SSD1322 grayscale OLED over 4-wire SPI.

    Args:
        spi: machine.SPI instance (mode 0, up to ~10 MHz)
        cs, dc, rst: machine.Pin outputs for chip select, data/command, reset
        width, height: panel size in pixels (default 256x64)
        col_offset: first RAM column used by the panel. The SSD1322 has RAM
            for 480 columns; a 256-wide module typically sits at columns
            0x1C..0x5B. Check the module datasheet.
        contrast: contrast current, 0x00-0xFF
    """

    def __init__(self, spi, cs, dc, rst, width=256, height=64,
                 col_offset=0x1C, contrast=0x9F):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.width = width
        self.height = height
        self.col_offset = col_offset
        # RAM columns hold 4 pixels each (2 bytes)
        self._col_start = col_offset
        self._col_end = col_offset + width // 4 - 1

        self.buffer = bytearray(width * height // 2)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, width, height, framebuf.GS4_HMSB
        )
        self._cmd_buf = bytearray(1)

        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=1)

        self.reset()
        self.init_display(contrast)

    # --- Low level -------------------------------------------------------

    def reset(self):
        """Hardware reset pulse."""
        self.rst.value(1)
        time.sleep_ms(1)
        self.rst.value(0)
        time.sleep_ms(10)
        self.rst.value(1)
        time.sleep_ms(10)

    def write_cmd(self, cmd, *args):
        """Write a command byte followed by optional argument bytes."""
        self.cs.value(0)
        self.dc.value(0)
        self._cmd_buf[0] = cmd
        self.spi.write(self._cmd_buf)
        if args:
            self.dc.value(1)
            self.spi.write(bytes(args))
        self.cs.value(1)

    def write_data(self, buf):
        """Write a data buffer (D/C high)."""
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(buf)
        self.cs.value(1)

    def init_display(self, contrast=0x9F):
        """Initialise the controller for a 256x64 panel with internal VDD regulator."""
        self.write_cmd(_SET_COMMAND_LOCK, 0x12)        # Unlock OLED driver IC
        self.write_cmd(_DISPLAY_OFF)
        self.write_cmd(_SET_CLOCK_DIV, 0x91)           # Divide by 2, osc freq 9
        self.write_cmd(_SET_MUX_RATIO, self.height - 1)
        self.write_cmd(_SET_DISPLAY_OFFSET, 0x00)
        self.write_cmd(_SET_START_LINE, 0x00)
        # Horizontal address increment, nibble remap (left pixel in the high
        # nibble), scan COM63..COM0, dual COM line mode for 64-row panels
        self.write_cmd(_SET_REMAP, 0x14, 0x11)
        self.write_cmd(_SET_GPIO, 0x00)                # GPIO0/1 inputs, disabled
        self.write_cmd(_SET_FUNCTION_SELECT, 0x01)     # Internal VDD regulator
        self.write_cmd(_SET_ENHANCEMENT_A, 0xA0, 0xFD) # External VSL, enhanced low-GS quality
        self.write_cmd(_SET_CONTRAST, contrast)
        self.write_cmd(_SET_MASTER_CONTRAST, 0x0F)     # Maximum
        self.write_cmd(_DEFAULT_GRAYSCALE)             # Linear grayscale table
        self.write_cmd(_SET_PHASE_LENGTH, 0xE2)        # Phase 1: 5 DCLK, phase 2: 14 DCLK
        self.write_cmd(_SET_ENHANCEMENT_B, 0x82, 0x20) # Reserved defaults
        self.write_cmd(_SET_PRECHARGE_VOLTAGE, 0x1F)   # 0.60 x VCC
        self.write_cmd(_SET_SECOND_PRECHARGE, 0x08)    # 8 DCLK
        self.write_cmd(_SET_VCOMH, 0x07)               # 0.86 x VCC
        self.write_cmd(_SET_DISPLAY_NORMAL)
        self.write_cmd(_EXIT_PARTIAL)
        self.fill(0)
        self.show()
        self.write_cmd(_DISPLAY_ON)

    # --- Control ---------------------------------------------------------

    def poweroff(self):
        """Turn the panel off (RAM contents are kept)."""
        self.write_cmd(_DISPLAY_OFF)

    def poweron(self):
        """Turn the panel on."""
        self.write_cmd(_DISPLAY_ON)

    def contrast(self, contrast):
        """Set contrast current (0-255)."""
        self.write_cmd(_SET_CONTRAST, contrast & 0xFF)

    def invert(self, invert):
        """Invert display gray levels."""
        self.write_cmd(_SET_DISPLAY_INVERSE if invert else _SET_DISPLAY_NORMAL)

    # --- Drawing (framebuf pass-through, colours are gray levels 0-15) ---

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col=None):
        if col is None:
            return self.framebuf.pixel(x, y)
        self.framebuf.pixel(x, y, col)

    def text(self, string, x, y, col=15):
        self.framebuf.text(string, x, y, col)

    def hline(self, x, y, w, col):
        self.framebuf.hline(x, y, w, col)

    def vline(self, x, y, h, col):
        self.framebuf.vline(x, y, h, col)

    def line(self, x1, y1, x2, y2, col):
        self.framebuf.line(x1, y1, x2, y2, col)

    def rect(self, x, y, w, h, col):
        self.framebuf.rect(x, y, w, h, col)

    def fill_rect(self, x, y, w, h, col):
        self.framebuf.fill_rect(x, y, w, h, col)

    def blit(self, fbuf, x, y, key=-1):
        self.framebuf.blit(fbuf, x, y, key)

    def show(self):
        """Send the whole frame buffer to the panel (8 KB for 256x64)."""
        self.write_cmd(_SET_COLUMN_ADDR, self._col_start, self._col_end)
        self.write_cmd(_SET_ROW_ADDR, 0, self.height - 1)
        self.write_cmd(_WRITE_RAM)
        self.write_data(self.buffer)
