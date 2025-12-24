# Sensor Module EEPROM Driver
# Handles reading/writing calibration data from AT24Cxx EEPROMs

from micropython import const
import struct
import time

# EEPROM constants
EEPROM_DEFAULT_ADDR = const(0x50)
EEPROM_PAGE_SIZE = const(8)  # AT24C02 page size
EEPROM_SIZE = const(256)     # AT24C02 = 256 bytes

# Data format constants
MAGIC = b'RFPM'
FORMAT_VERSION = const(1)

# Offsets in EEPROM
OFF_MAGIC = const(0)         # 4 bytes: 'RFPM'
OFF_VERSION = const(4)       # 1 byte: format version
OFF_TYPE_LEN = const(5)      # 1 byte: sensor type string length
OFF_TYPE = const(6)          # 8 bytes: sensor type string
OFF_SERIAL_LEN = const(14)   # 1 byte: serial number length
OFF_SERIAL = const(15)       # 12 bytes: serial number string
OFF_SLOPE = const(27)        # 4 bytes: base slope (float)
OFF_INTERCEPT = const(31)    # 4 bytes: base intercept (float)
OFF_NUM_FREQS = const(35)    # 1 byte: number of frequencies
OFF_FREQS = const(36)        # 2 bytes each: frequency in MHz (max 16 = 32 bytes)
OFF_CAL_DATA = const(68)     # Start of per-frequency calibration data

# Per-frequency calibration entry: 2 + 4 + 4 = 10 bytes each
# freq(2) + offset(4) + slope(4)
CAL_ENTRY_SIZE = const(10)
MAX_FREQUENCIES = const(16)
MAX_CAL_ENTRIES = const(18)  # (256 - 68) / 10 = 18


class SensorEEPROM:
    """Driver for sensor module EEPROM."""

    def __init__(self, i2c, address=EEPROM_DEFAULT_ADDR):
        """
        Initialize EEPROM driver.

        Args:
            i2c: I2C bus instance
            address: EEPROM I2C address
        """
        self.i2c = i2c
        self.address = address

    def _write_byte(self, addr, data):
        """Write a single byte to EEPROM."""
        self.i2c.writeto(self.address, bytes([addr, data]))
        time.sleep_ms(5)  # Write cycle time

    def _write_page(self, addr, data):
        """Write up to 8 bytes (one page) to EEPROM."""
        if len(data) > EEPROM_PAGE_SIZE:
            raise ValueError("Data exceeds page size")
        self.i2c.writeto(self.address, bytes([addr]) + data)
        time.sleep_ms(5)  # Write cycle time

    def _read_bytes(self, addr, length):
        """Read bytes from EEPROM."""
        self.i2c.writeto(self.address, bytes([addr]))
        return self.i2c.readfrom(self.address, length)

    def write_bytes(self, addr, data):
        """Write data to EEPROM, handling page boundaries."""
        data = bytes(data)
        offset = 0

        while offset < len(data):
            # Calculate bytes until page boundary
            page_offset = (addr + offset) % EEPROM_PAGE_SIZE
            bytes_to_write = min(EEPROM_PAGE_SIZE - page_offset, len(data) - offset)

            self._write_page(addr + offset, data[offset:offset + bytes_to_write])
            offset += bytes_to_write

    def is_valid(self):
        """Check if EEPROM contains valid sensor data."""
        try:
            magic = self._read_bytes(OFF_MAGIC, 4)
            return magic == MAGIC
        except OSError:
            return False

    def is_present(self):
        """Check if EEPROM is present on I2C bus."""
        try:
            self.i2c.writeto(self.address, bytes([0]))
            return True
        except OSError:
            return False

    def read_sensor_info(self):
        """
        Read sensor information from EEPROM.

        Returns:
            Dict with sensor info or None if invalid
        """
        if not self.is_valid():
            return None

        try:
            # Read header
            version = self._read_bytes(OFF_VERSION, 1)[0]
            if version != FORMAT_VERSION:
                return None

            # Read sensor type
            type_len = self._read_bytes(OFF_TYPE_LEN, 1)[0]
            sensor_type = self._read_bytes(OFF_TYPE, type_len).decode('utf-8')

            # Read serial number
            serial_len = self._read_bytes(OFF_SERIAL_LEN, 1)[0]
            serial = self._read_bytes(OFF_SERIAL, serial_len).decode('utf-8')

            # Read base calibration
            slope_bytes = self._read_bytes(OFF_SLOPE, 4)
            slope = struct.unpack('<f', slope_bytes)[0]

            intercept_bytes = self._read_bytes(OFF_INTERCEPT, 4)
            intercept = struct.unpack('<f', intercept_bytes)[0]

            # Read frequencies
            num_freqs = self._read_bytes(OFF_NUM_FREQS, 1)[0]
            freq_bytes = self._read_bytes(OFF_FREQS, num_freqs * 2)
            frequencies = []
            for i in range(num_freqs):
                freq = struct.unpack('<H', freq_bytes[i*2:i*2+2])[0]
                frequencies.append(freq)

            return {
                'type': sensor_type,
                'serial': serial,
                'slope': slope,
                'intercept': intercept,
                'frequencies': frequencies,
            }
        except (OSError, UnicodeError, struct.error):
            return None

    def read_calibration(self):
        """
        Read per-frequency calibration data.

        Returns:
            Dict mapping frequency to (offset, slope) or empty dict
        """
        cal_data = {}

        try:
            # First read number of calibration entries
            # It's stored as first byte of cal data area
            num_entries = self._read_bytes(OFF_CAL_DATA, 1)[0]

            if num_entries == 0 or num_entries > MAX_CAL_ENTRIES:
                return cal_data

            # Read calibration entries
            for i in range(num_entries):
                entry_addr = OFF_CAL_DATA + 1 + (i * CAL_ENTRY_SIZE)
                entry_bytes = self._read_bytes(entry_addr, CAL_ENTRY_SIZE)

                freq = struct.unpack('<H', entry_bytes[0:2])[0]
                offset = struct.unpack('<f', entry_bytes[2:6])[0]
                slope = struct.unpack('<f', entry_bytes[6:10])[0]

                cal_data[freq] = {'offset': offset, 'slope': slope}

        except (OSError, struct.error):
            pass

        return cal_data

    def write_sensor_info(self, sensor_type, serial, slope, intercept, frequencies):
        """
        Write sensor information to EEPROM.

        Args:
            sensor_type: Sensor type string (max 8 chars)
            serial: Serial number string (max 12 chars)
            slope: Base slope (mV/dB)
            intercept: Base intercept (dBm)
            frequencies: List of calibration frequencies in MHz
        """
        sensor_type = sensor_type[:8]
        serial = serial[:12]
        frequencies = frequencies[:MAX_FREQUENCIES]

        # Write magic and version
        self.write_bytes(OFF_MAGIC, MAGIC)
        self._write_byte(OFF_VERSION, FORMAT_VERSION)

        # Write sensor type
        type_bytes = sensor_type.encode('utf-8')
        self._write_byte(OFF_TYPE_LEN, len(type_bytes))
        self.write_bytes(OFF_TYPE, type_bytes)

        # Write serial
        serial_bytes = serial.encode('utf-8')
        self._write_byte(OFF_SERIAL_LEN, len(serial_bytes))
        self.write_bytes(OFF_SERIAL, serial_bytes)

        # Write base calibration
        self.write_bytes(OFF_SLOPE, struct.pack('<f', slope))
        self.write_bytes(OFF_INTERCEPT, struct.pack('<f', intercept))

        # Write frequencies
        self._write_byte(OFF_NUM_FREQS, len(frequencies))
        freq_bytes = b''
        for freq in frequencies:
            freq_bytes += struct.pack('<H', freq)
        self.write_bytes(OFF_FREQS, freq_bytes)

        # Initialize calibration data area (0 entries)
        self._write_byte(OFF_CAL_DATA, 0)

    def write_calibration(self, cal_data):
        """
        Write per-frequency calibration data.

        Args:
            cal_data: Dict mapping frequency to {'offset': float, 'slope': float}
        """
        # Filter to only non-default entries
        entries = []
        for freq, cal in cal_data.items():
            offset = cal.get('offset', 0.0)
            slope = cal.get('slope', 1.0)
            # Only store if not default values
            if abs(offset) > 0.001 or abs(slope - 1.0) > 0.001:
                entries.append((freq, offset, slope))

        if len(entries) > MAX_CAL_ENTRIES:
            entries = entries[:MAX_CAL_ENTRIES]

        # Write number of entries
        self._write_byte(OFF_CAL_DATA, len(entries))

        # Write each entry
        for i, (freq, offset, slope) in enumerate(entries):
            entry_addr = OFF_CAL_DATA + 1 + (i * CAL_ENTRY_SIZE)
            entry_bytes = struct.pack('<H', freq) + struct.pack('<f', offset) + struct.pack('<f', slope)
            self.write_bytes(entry_addr, entry_bytes)

    def erase(self):
        """Erase EEPROM (fill with 0xFF)."""
        for addr in range(0, EEPROM_SIZE, EEPROM_PAGE_SIZE):
            self._write_page(addr, bytes([0xFF] * EEPROM_PAGE_SIZE))

    def format_new_sensor(self, sensor_type, serial, slope, intercept, frequencies):
        """
        Format EEPROM for a new sensor module.

        Args:
            sensor_type: Sensor type (e.g., "AD8307")
            serial: Unique serial number
            slope: Base slope in V/dB
            intercept: Base intercept in dBm
            frequencies: List of calibration frequencies in MHz
        """
        self.erase()
        self.write_sensor_info(sensor_type, serial, slope, intercept, frequencies)
