# Bitmap Fonts

`make_fonts.py` renders the B612 TrueType fonts in `../../fonts/` into
4-bit antialiased bitmap fonts for the SSD1322 and writes them as
MicroPython modules to `src/display/fonts/`. The firmware draws them with
`src/display/bitmapfont.py`.

```
pip install pillow
python3 tools/fonts/make_fonts.py                 # regenerate all fonts
python3 tools/fonts/make_fonts.py --preview /tmp  # plus 4x PNG previews
```

Fonts, sizes and character sets are listed in `FONTS` at the top of the
script. Sizes are em sizes in px. Digits always get a common integer
advance (tabular figures), so right-aligned readings do not jitter. The
30 px font only holds ` +-.0123456789` to save RAM; add characters there
if the large font needs more.

Commit the generated modules together with the firmware.
