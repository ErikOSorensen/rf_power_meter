# Desktop stand-in for MicroPython's framebuf module
#
# Pure Python, GS4_HMSB only: enough to run the display drawing code
# (display/bitmapfont.py etc.) under CPython and save the result as an
# image. Put this directory on sys.path ahead of src/ to use it.
#
# Follows MicroPython's semantics, including blit(): the source pixel is
# looked up in the palette first, then compared with key.

GS4_HMSB = 2


class FrameBuffer:
    def __init__(self, buf, width, height, format, stride=None):
        if format != GS4_HMSB:
            raise ValueError("desktop framebuf only supports GS4_HMSB")
        self.buf = buf
        self.width = width
        self.height = height
        self.stride = width if stride is None else stride

    # GS4_HMSB: two pixels per byte, left pixel in the high nibble.
    # Like MicroPython, the offset is (x + y * stride) // 2, so rows only
    # start on a byte boundary when stride is even.
    def _get(self, x, y):
        i = x + y * self.stride
        b = self.buf[i >> 1]
        return b & 0x0F if i & 1 else b >> 4

    def _set(self, x, y, c):
        i = x + y * self.stride
        b = self.buf[i >> 1]
        if i & 1:
            self.buf[i >> 1] = (b & 0xF0) | (c & 0x0F)
        else:
            self.buf[i >> 1] = (b & 0x0F) | ((c & 0x0F) << 4)

    def pixel(self, x, y, c=None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None if c is None else None
        if c is None:
            return self._get(x, y)
        self._set(x, y, c)

    def fill(self, c):
        self.fill_rect(0, 0, self.width, self.height, c)

    def fill_rect(self, x, y, w, h, c):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.width), min(y + h, self.height)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                self._set(xx, yy, c)

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def rect(self, x, y, w, h, c, f=False):
        if f:
            self.fill_rect(x, y, w, h, c)
            return
        self.hline(x, y, w, c)
        self.hline(x, y + h - 1, w, c)
        self.vline(x, y, h, c)
        self.vline(x + w - 1, y, h, c)

    def blit(self, fbuf, x, y, key=-1, palette=None):
        for sy in range(fbuf.height):
            dy = y + sy
            if not 0 <= dy < self.height:
                continue
            for sx in range(fbuf.width):
                dx = x + sx
                if not 0 <= dx < self.width:
                    continue
                c = fbuf._get(sx, sy)
                if palette is not None:
                    c = palette._get(c, 0)
                if c != key:
                    self._set(dx, dy, c)

    def text(self, s, x, y, c=1):
        raise NotImplementedError("built-in 8x8 font is not emulated")
