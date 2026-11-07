# Desktop Tools

Host-side scripts that run on a PC under CPython, never on the Pico.
Typical uses: generating font bitmaps for the display, writing
calibration data to sensor head EEPROMs, and talking to the meter over
SCPI for testing.

Code here may use any desktop library (Pillow, NumPy, pyvisa, ...).
Nothing in this directory is copied to the Pico. When a tool generates
something the firmware needs, such as a font module, it writes the result
into `../src/` and that generated file is committed with the firmware.

Put each tool in its own subdirectory (e.g. `fonts/`) with a short note
on how to run it and what it produces.
