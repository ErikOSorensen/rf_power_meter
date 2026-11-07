#!/usr/bin/env python3
"""
Generate anti-aliased 4-bit bitmap fonts for the SSD1322 display.

Renders TrueType glyphs with Pillow and writes one MicroPython module per
font into src/display/fonts/. The firmware draws them with
src/display/bitmapfont.py.

Usage (from the repository root):

    python3 tools/fonts/make_fonts.py              # build all fonts in FONTS
    python3 tools/fonts/make_fonts.py --preview    # also write PNG previews

Sizes are em sizes in pixels, as in CSS "font-size: 30px". The script
prints the resulting digit height and line height for each font.

Pixel format: 4 bits per pixel, two pixels per byte, left pixel in the
high nibble (framebuf.GS4_HMSB, the SSD1322's own RAM layout). The value
is glyph coverage, 0 = background, 15 = full ink. Each glyph bitmap is
trimmed to its ink and padded to an even width, so every row starts on a
byte boundary.

Requires: Pillow
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FONT_DIR = os.path.join(ROOT, "fonts")
OUT_DIR = os.path.join(ROOT, "src", "display", "fonts")

ASCII = "".join(chr(c) for c in range(32, 127))
SYMBOLS = "°µ±Ω"
DIGITS = "0123456789"

# (module name, TTF file, size in px, characters)
# The large font only holds what the main reading needs, to save RAM.
FONTS = [
    ("b612_bold_30", "B612-Bold.ttf", 30, " +-.0123456789"),
    ("b612_regular_12", "B612-Regular.ttf", 12, ASCII + SYMBOLS),
    ("b612_regular_9", "B612-Regular.ttf", 9, ASCII + SYMBOLS),
]

RECORD_SIZE = 8   # Bytes per glyph in INDEX


def render_glyph(font, ch, ascent, mono):
    """
    Render one glyph.

    Returns (advance, xoff, yoff, width, height, pixels) where pixels is a
    list of rows of 4-bit coverage values, and xoff/yoff place the bitmap
    relative to the pen position at the top of the line.
    """
    advance = font.getlength(ch)
    # Box of the ink with the pen at (0, 0) and y = 0 at the top of the line
    x0, y0, x1, y1 = font.getbbox(ch, anchor="ls")
    y0 += ascent
    y1 += ascent
    if x1 <= x0 or y1 <= y0:
        return advance, 0, 0, 0, 0, []

    w, h = x1 - x0, y1 - y0
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1" if mono else "L"
    draw.text((-x0, ascent - y0), ch, font=font, fill=255, anchor="ls")

    px = img.load()
    rows = [[(px[x, y] * 15 + 127) // 255 for x in range(w)] for y in range(h)]

    # Trim empty rows/columns left by antialiasing rounding
    while rows and not any(rows[0]):
        rows.pop(0)
        y0 += 1
    while rows and not any(rows[-1]):
        rows.pop()
    if not rows:
        return advance, 0, 0, 0, 0, []
    while not any(r[0] for r in rows):
        rows = [r[1:] for r in rows]
        x0 += 1
    while not any(r[-1] for r in rows):
        rows = [r[:-1] for r in rows]

    if len(rows[0]) % 2:
        rows = [r + [0] for r in rows]
    return advance, x0, y0, len(rows[0]), len(rows), rows


def pack_rows(rows):
    """Pack rows of 4-bit values into GS4_HMSB bytes."""
    out = bytearray()
    for r in rows:
        for i in range(0, len(r), 2):
            out.append((r[i] << 4) | r[i + 1])
    return out


def build_font(ttf, size, chars, mono=False):
    font = ImageFont.truetype(ttf, size)
    ascent, descent = font.getmetrics()

    glyphs = {}
    for ch in chars:
        glyphs[ch] = list(render_glyph(font, ch, ascent, mono))

    # Integer advances. Digits all get the same cell width (tabular).
    for g in glyphs.values():
        g[0] = int(round(g[0]))
    digits = [c for c in DIGITS if c in glyphs]
    if digits:
        tab = max(glyphs[c][0] for c in digits)
        for c in digits:
            glyphs[c][0] = tab

    index = bytearray()
    data = bytearray()
    for ch in chars:
        advance, xoff, yoff, w, h, rows = glyphs[ch]
        for v, lo, hi in ((advance, 0, 255), (xoff, -128, 127),
                          (yoff, -128, 127), (w, 0, 255), (h, 0, 255)):
            if not lo <= v <= hi:
                raise ValueError("glyph %r: value %d out of range" % (ch, v))
        offset = len(data)
        if offset > 0xFFFF:
            raise ValueError("font data exceeds 64 KB")
        index += bytes((advance, xoff & 0xFF, yoff & 0xFF, w, h, 0,
                        offset & 0xFF, offset >> 8))
        data += pack_rows(rows)

    return {
        "height": ascent + descent,
        "baseline": ascent,
        "digit_height": (font.getbbox("0", anchor="ls")[3]
                         - font.getbbox("0", anchor="ls")[1]),
        "digit_width": glyphs[digits[0]][0] if digits else None,
        "chars": chars,
        "index": bytes(index),
        "data": bytes(data),
    }


def bytes_literal(b, indent="    ", width=76):
    """Format bytes as a wrapped b"..." literal using \\x escapes."""
    s = "".join("\\x%02x" % v for v in b)
    per_line = (width - len(indent) - 3) // 4 * 4
    lines = [s[i:i + per_line] for i in range(0, len(s), per_line)] or [""]
    return "\n".join('%sb"%s"' % (indent, ln) for ln in lines)


def write_module(path, name, ttf, size, font, mono):
    chars = font["chars"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("# %s: %s at %d px%s\n" % (name, os.path.basename(ttf), size,
                                            ", 1-bit" if mono else ""))
        f.write("# Generated by tools/fonts/make_fonts.py. Do not edit.\n")
        f.write("# B612 is licensed under the SIL Open Font License 1.1 "
                "(see fonts/OFL.txt).\n")
        f.write("#\n")
        f.write("# Draw with display.bitmapfont.BitmapFont. INDEX holds %d bytes\n"
                % RECORD_SIZE)
        f.write("# per glyph, in CHARS order: advance, x offset (signed), y offset\n")
        f.write("# (signed, from the top of the line), width, height, 0, data\n")
        f.write("# offset (16-bit little endian). DATA is GS4_HMSB, row-major.\n\n")
        f.write("HEIGHT = %d\n" % font["height"])
        f.write("BASELINE = %d\n" % font["baseline"])
        f.write("CHARS = %r\n" % chars)
        f.write("INDEX = (\n%s\n)\n" % bytes_literal(font["index"]))
        # bytearray: framebuf needs a writable buffer. Frozen, the literal
        # stays in flash and only the bytearray copy is in RAM.
        f.write("DATA = bytearray(\n%s\n)\n" % bytes_literal(font["data"]))


def preview(path, font, text, scale=4):
    """Render text the way bitmapfont.py does, for checking on the desktop."""
    chars, index, data = font["chars"], font["index"], font["data"]
    width = 0
    for ch in text:
        i = chars.find(ch)
        width += index[i * RECORD_SIZE] if i >= 0 else 0
    img = Image.new("L", (max(width, 1) + 4, font["height"] + 4), 0)
    px = img.load()
    x = 2
    for ch in text:
        i = chars.find(ch)
        if i < 0:
            continue
        r = index[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        adv, xoff, yoff, w, h = r[0], r[1] - 256 * (r[1] > 127), \
            r[2] - 256 * (r[2] > 127), r[3], r[4]
        off = r[6] | (r[7] << 8)
        for gy in range(h):
            for gx in range(w):
                b = data[off + (gy * w + gx) // 2]
                v = b >> 4 if gx % 2 == 0 else b & 0x0F
                if v:
                    px[x + xoff + gx, 2 + yoff + gy] = v * 17
        x += adv
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description="Generate 4-bit bitmap fonts for the SSD1322 display.")
    ap.add_argument("--preview", metavar="DIR", nargs="?", const=".",
                    help="write a PNG preview of each font into DIR")
    ap.add_argument("--mono", action="store_true",
                    help="1-bit rendering (no antialiasing)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    init = os.path.join(OUT_DIR, "__init__.py")
    if not os.path.exists(init):
        with open(init, "w") as f:
            f.write("# Generated bitmap fonts, see tools/fonts/make_fonts.py\n")

    for name, ttf_name, size, chars in FONTS:
        ttf = os.path.join(FONT_DIR, ttf_name)
        font = build_font(ttf, size, chars, args.mono)
        out = os.path.join(OUT_DIR, name + ".py")
        write_module(out, name, ttf, size, font, args.mono)
        print("%-16s line %2d px, digits %2d px tall x %s px wide, "
              "%d glyphs, %d bytes bitmap -> %s"
              % (name, font["height"], font["digit_height"], font["digit_width"],
                 len(chars), len(font["data"]), os.path.relpath(out, ROOT)))
        if args.preview:
            sample = chars if len(chars) < 20 else (
                "CH1 23.4°C AD8307 433MHz -12.34 dBm +40dB 0123456789")
            png = os.path.join(args.preview, name + ".png")
            preview(png, font, sample)
            print("%16s preview -> %s" % ("", png))


if __name__ == "__main__":
    sys.exit(main())
