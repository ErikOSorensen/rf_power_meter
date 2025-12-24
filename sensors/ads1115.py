# ADS1115 16-bit ADC Driver for MicroPython
# Supports differential and single-ended readings

from micropython import const
import struct
import time

# Register addresses
_REG_CONVERSION = const(0x00)
_REG_CONFIG = const(0x01)

# Config register bits
_OS_SINGLE = const(0x8000)      # Start single conversion
_OS_BUSY = const(0x0000)        # Device is busy
_OS_NOTBUSY = const(0x8000)     # Device is not busy

# Mux settings for differential readings
_MUX_DIFF_0_1 = const(0x0000)   # AIN0 - AIN1 (power reading)
_MUX_DIFF_2_3 = const(0x3000)   # AIN2 - AIN3 (sensor ID)

# Mux settings for single-ended readings
_MUX_SINGLE_0 = const(0x4000)
_MUX_SINGLE_1 = const(0x5000)
_MUX_SINGLE_2 = const(0x6000)
_MUX_SINGLE_3 = const(0x7000)

# Programmable Gain Amplifier settings
PGA_6_144V = const(0x0000)      # +/- 6.144V (187.5uV/bit)
PGA_4_096V = const(0x0200)      # +/- 4.096V (125uV/bit)
PGA_2_048V = const(0x0400)      # +/- 2.048V (62.5uV/bit) - default
PGA_1_024V = const(0x0600)      # +/- 1.024V (31.25uV/bit)
PGA_0_512V = const(0x0800)      # +/- 0.512V (15.625uV/bit)
PGA_0_256V = const(0x0A00)      # +/- 0.256V (7.8125uV/bit)

# PGA voltage ranges for conversion
_PGA_RANGE = {
    PGA_6_144V: 6.144,
    PGA_4_096V: 4.096,
    PGA_2_048V: 2.048,
    PGA_1_024V: 1.024,
    PGA_0_512V: 0.512,
    PGA_0_256V: 0.256,
}

# Data rates
RATE_8 = const(0x0000)          # 8 SPS
RATE_16 = const(0x0020)         # 16 SPS
RATE_32 = const(0x0040)         # 32 SPS
RATE_64 = const(0x0060)         # 64 SPS
RATE_128 = const(0x0080)        # 128 SPS - default
RATE_250 = const(0x00A0)        # 250 SPS
RATE_475 = const(0x00C0)        # 475 SPS
RATE_860 = const(0x00E0)        # 860 SPS

# Conversion delays (ms) for each rate
_RATE_DELAY = {
    RATE_8: 130,
    RATE_16: 65,
    RATE_32: 35,
    RATE_64: 20,
    RATE_128: 10,
    RATE_250: 5,
    RATE_475: 3,
    RATE_860: 2,
}

# Mode
_MODE_CONTINUOUS = const(0x0000)
_MODE_SINGLE = const(0x0100)

# Comparator (disabled)
_COMP_DISABLE = const(0x0003)


class ADS1115:
    """ADS1115 16-bit ADC driver."""

    def __init__(self, i2c, address=0x48, gain=PGA_4_096V, rate=RATE_128):
        """
        Initialize ADS1115.

        Args:
            i2c: I2C bus instance
            address: I2C address (0x48-0x4B)
            gain: PGA gain setting
            rate: Data rate setting
        """
        self.i2c = i2c
        self.address = address
        self.gain = gain
        self.rate = rate
        self._buffer = bytearray(3)

    def _write_register(self, reg, value):
        """Write 16-bit value to register."""
        self._buffer[0] = reg
        self._buffer[1] = (value >> 8) & 0xFF
        self._buffer[2] = value & 0xFF
        self.i2c.writeto(self.address, self._buffer)

    def _read_register(self, reg):
        """Read 16-bit value from register."""
        self.i2c.writeto(self.address, bytes([reg]))
        data = self.i2c.readfrom(self.address, 2)
        return struct.unpack('>h', data)[0]

    def _read_raw(self, mux):
        """
        Start conversion and read raw ADC value.

        Args:
            mux: Multiplexer configuration

        Returns:
            Signed 16-bit ADC value
        """
        config = (_OS_SINGLE | mux | self.gain |
                  _MODE_SINGLE | self.rate | _COMP_DISABLE)
        self._write_register(_REG_CONFIG, config)

        # Wait for conversion
        delay = _RATE_DELAY.get(self.rate, 10)
        time.sleep_ms(delay)

        # Poll for completion (backup)
        for _ in range(10):
            if self._read_register(_REG_CONFIG) & _OS_NOTBUSY:
                break
            time.sleep_ms(1)

        return self._read_register(_REG_CONVERSION)

    def read_diff_0_1(self):
        """Read differential voltage between AIN0 and AIN1 (power sensor)."""
        raw = self._read_raw(_MUX_DIFF_0_1)
        return self._raw_to_voltage(raw)

    def read_diff_2_3(self):
        """Read differential voltage between AIN2 and AIN3 (sensor ID)."""
        raw = self._read_raw(_MUX_DIFF_2_3)
        return self._raw_to_voltage(raw)

    def read_single(self, channel):
        """
        Read single-ended voltage on specified channel.

        Args:
            channel: ADC channel (0-3)

        Returns:
            Voltage in volts
        """
        mux = [_MUX_SINGLE_0, _MUX_SINGLE_1, _MUX_SINGLE_2, _MUX_SINGLE_3][channel]
        raw = self._read_raw(mux)
        return self._raw_to_voltage(raw)

    def _raw_to_voltage(self, raw):
        """Convert raw ADC value to voltage."""
        voltage_range = _PGA_RANGE.get(self.gain, 2.048)
        return raw * voltage_range / 32767.0

    def read_power_voltage(self):
        """Read power sensor voltage (differential A0-A1)."""
        return self.read_diff_0_1()

    def read_id_voltage(self):
        """Read sensor ID voltage (differential A2-A3)."""
        return self.read_diff_2_3()

    def set_gain(self, gain):
        """Set PGA gain."""
        self.gain = gain

    def set_rate(self, rate):
        """Set data rate."""
        self.rate = rate
