# SSD1306 OLED Driver for MicroPython
# Supports 128x64 and 128x32 displays via I2C

from micropython import const
import framebuf

# Commands
_SET_CONTRAST = const(0x81)
_SET_ENTIRE_ON = const(0xA4)
_SET_NORM_INV = const(0xA6)
_SET_DISP = const(0xAE)
_SET_MEM_ADDR = const(0x20)
_SET_COL_ADDR = const(0x21)
_SET_PAGE_ADDR = const(0x22)
_SET_DISP_START_LINE = const(0x40)
_SET_SEG_REMAP = const(0xA0)
_SET_MUX_RATIO = const(0xA8)
_SET_COM_OUT_DIR = const(0xC0)
_SET_DISP_OFFSET = const(0xD3)
_SET_COM_PIN_CFG = const(0xDA)
_SET_DISP_CLK_DIV = const(0xD5)
_SET_PRECHARGE = const(0xD9)
_SET_VCOM_DESEL = const(0xDB)
_SET_CHARGE_PUMP = const(0x8D)


class SSD1306:
    """SSD1306 OLED display driver base class."""

    def __init__(self, width, height, external_vcc=False):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = height // 8
        self.buffer = bytearray(self.pages * width)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, width, height, framebuf.MONO_VLSB
        )
        self.init_display()

    def init_display(self):
        """Initialize display with standard configuration."""
        for cmd in (
            _SET_DISP | 0x00,  # Display off
            _SET_MEM_ADDR, 0x00,  # Horizontal addressing mode
            _SET_DISP_START_LINE | 0x00,
            _SET_SEG_REMAP | 0x01,  # Column 127 mapped to SEG0
            _SET_MUX_RATIO, self.height - 1,
            _SET_COM_OUT_DIR | 0x08,  # Scan from COM[N-1] to COM0
            _SET_DISP_OFFSET, 0x00,
            _SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            _SET_DISP_CLK_DIV, 0x80,
            _SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            _SET_VCOM_DESEL, 0x30,
            _SET_CONTRAST, 0xFF,
            _SET_ENTIRE_ON,  # Output follows RAM contents
            _SET_NORM_INV,  # Not inverted
            _SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            _SET_DISP | 0x01,  # Display on
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        """Turn off display."""
        self.write_cmd(_SET_DISP | 0x00)

    def poweron(self):
        """Turn on display."""
        self.write_cmd(_SET_DISP | 0x01)

    def contrast(self, contrast):
        """Set display contrast (0-255)."""
        self.write_cmd(_SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        """Invert display colors."""
        self.write_cmd(_SET_NORM_INV | (invert & 1))

    def fill(self, col):
        """Fill entire display with color (0 or 1)."""
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        """Set pixel at x, y to color."""
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        """Scroll display by dx, dy pixels."""
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        """Draw text at x, y."""
        self.framebuf.text(string, x, y, col)

    def hline(self, x, y, w, col):
        """Draw horizontal line."""
        self.framebuf.hline(x, y, w, col)

    def vline(self, x, y, h, col):
        """Draw vertical line."""
        self.framebuf.vline(x, y, h, col)

    def line(self, x1, y1, x2, y2, col):
        """Draw line from (x1,y1) to (x2,y2)."""
        self.framebuf.line(x1, y1, x2, y2, col)

    def rect(self, x, y, w, h, col):
        """Draw rectangle outline."""
        self.framebuf.rect(x, y, w, h, col)

    def fill_rect(self, x, y, w, h, col):
        """Draw filled rectangle."""
        self.framebuf.fill_rect(x, y, w, h, col)

    def blit(self, fbuf, x, y):
        """Blit framebuffer at x, y."""
        self.framebuf.blit(fbuf, x, y)

    def show(self):
        """Update display with buffer contents."""
        self.write_cmd(_SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)
        self.write_cmd(_SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    """SSD1306 OLED display driver for I2C interface."""

    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b'\x40', None]  # Co=0, D/C#=1
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        """Write command byte."""
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        """Write data buffer."""
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)
