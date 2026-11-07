# Test screens, drawn with the firmware's own layout (display/layout.py)
#
# Runs on the Pico and on the desktop:
#
#   mpremote run tests/test_screen.py        # on the Pico (src/ deployed),
#                                            # shows the main screen on the OLED
#   python3 tests/test_screen.py [out.png [scale [screen]]]
#                                            # on the desktop, writes a PNG
#                                            # (default 4x scale), needs Pillow
#
# screen is one of: main (default), edit, nosensor, startup, error

try:
    import framebuf                      # MicroPython
    ON_PICO = True
except ImportError:
    import os
    import sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(_root, "src"))
    sys.path.insert(0, os.path.join(_root, "tools", "sim"))  # desktop stand-ins
    import framebuf
    ON_PICO = False

from display import layout


def draw_main(target, ch1_edit=None, ch2_sensor=True):
    target.fill(0)
    layout.draw_channel(target, 0, 1, -23.43, "dBm", "AD8307", 23.4,
                        137, 20, ch1_edit)
    if ch2_sensor:
        layout.draw_channel(target, layout.ROW_H, 2, -31.79, "dBm",
                            "AD8307", 24.1, 143, 3)
    else:
        layout.draw_channel(target, layout.ROW_H, 2, None, "dBm",
                            None, None, None, 0)


def draw_edit(target):
    draw_main(target, ch1_edit="freq")
    layout.draw_lock(target)


SCREENS = {
    "main": draw_main,
    "edit": draw_edit,
    "nosensor": lambda t: draw_main(t, ch2_sensor=False),
    "startup": lambda t: layout.draw_startup(t, "192.168.1.100"),
    "error": lambda t: layout.draw_error(
        t, "Sensor head on channel 2 does not answer on I2C, check the cable"),
}


def save_png(fb, path, scale=4):
    from PIL import Image
    w, h = layout.WIDTH, layout.HEIGHT
    img = Image.new("L", (w, h))
    img.putdata([fb.pixel(x, y) * 17 for y in range(h) for x in range(w)])
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    img.save(path)


def main():
    if ON_PICO:
        from display.power_display import DisplayManager
        display = DisplayManager().display
        draw_main(display)
        display.show()
        print("Test screen shown")
    else:
        out = sys.argv[1] if len(sys.argv) > 1 else "test_screen.png"
        scale = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        screen = sys.argv[3] if len(sys.argv) > 3 else "main"
        fb = framebuf.FrameBuffer(bytearray(layout.WIDTH * layout.HEIGHT // 2),
                                  layout.WIDTH, layout.HEIGHT, framebuf.GS4_HMSB)
        SCREENS[screen](fb)
        save_png(fb, out, scale)
        print("Wrote", out)


main()
