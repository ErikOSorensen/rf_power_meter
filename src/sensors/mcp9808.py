# MCP9808 I2C Temperature Sensor Driver for MicroPython
# One sits in every sensor head, next to the RF detector, so the detector's
# temperature drift can be characterised and compensated.

from micropython import const

MCP9808_DEFAULT_ADDR = const(0x18)  # A0-A2 to GND

_REG_CONFIG = const(0x01)
_REG_TA = const(0x05)           # Ambient temperature
_REG_MANUF_ID = const(0x06)     # Reads 0x0054
_REG_DEVICE_ID = const(0x07)    # Reads 0x04xx
_REG_RESOLUTION = const(0x08)

_MANUF_ID = const(0x0054)
_DEVICE_ID = const(0x04)

RES_0_5 = const(0x00)       # 0.5 C,    30 ms conversion
RES_0_25 = const(0x01)      # 0.25 C,   65 ms
RES_0_125 = const(0x02)     # 0.125 C,  130 ms
RES_0_0625 = const(0x03)    # 0.0625 C, 250 ms (power-up default)


class MCP9808:
    """MCP9808 temperature sensor driver."""

    def __init__(self, i2c, address=MCP9808_DEFAULT_ADDR):
        """
        Initialize driver. Does not touch the bus; the device may not be
        reachable until its sensor head is selected on the multiplexer.

        Args:
            i2c: I2C bus instance
            address: I2C address (0x18-0x1F)
        """
        self.i2c = i2c
        self.address = address

    def _read_register(self, reg):
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        return (data[0] << 8) | data[1]

    def _write_register8(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value & 0xFF]))

    def is_present(self):
        """Return True if an MCP9808 answers at this address."""
        try:
            return (self._read_register(_REG_MANUF_ID) == _MANUF_ID and
                    (self._read_register(_REG_DEVICE_ID) >> 8) == _DEVICE_ID)
        except OSError:
            return False

    def set_resolution(self, resolution=RES_0_0625):
        """Set conversion resolution (RES_* constants)."""
        self._write_register8(_REG_RESOLUTION, resolution)

    def read_temperature(self):
        """
        Read ambient temperature.

        Returns:
            Temperature in degrees Celsius (float)
        """
        raw = self._read_register(_REG_TA)
        upper = (raw >> 8) & 0x1F   # Drop alert flag bits
        lower = raw & 0xFF
        temp = (upper & 0x0F) * 16.0 + lower / 16.0
        if upper & 0x10:            # Sign bit
            temp -= 256.0
        return temp
