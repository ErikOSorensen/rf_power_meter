# Calibration Management with EEPROM Storage
# Reads/writes calibration from sensor module EEPROMs, one I2C bus per head

from .eeprom import SensorEEPROM, EEPROM_DEFAULT_ADDR
import config


class FrequencyCalibration:
    """Stores calibration corrections for a specific frequency."""

    def __init__(self, frequency_mhz, offset=0.0, slope=1.0):
        """
        Initialize frequency calibration point.

        Args:
            frequency_mhz: Frequency in MHz
            offset: Offset correction in dB
            slope: Slope correction factor (1.0 = no correction)
        """
        self.frequency = frequency_mhz
        self.offset = offset
        self.slope = slope


class SensorCalibration:
    """Calibration data for a single sensor module."""

    def __init__(self, sensor_type, serial, base_slope, base_intercept, frequencies):
        """
        Initialize sensor calibration.

        Args:
            sensor_type: Sensor type string (e.g., "AD8307")
            serial: Sensor serial number
            base_slope: Base mV/dB slope
            base_intercept: Base dBm intercept
            frequencies: List of calibration frequencies in MHz
        """
        self.sensor_type = sensor_type
        self.serial = serial
        self.base_slope = base_slope
        self.base_intercept = base_intercept
        self.frequencies = sorted(frequencies) if frequencies else []

        # Current operating frequency (defaults to lowest). May lie between
        # calibration points; corrections are then interpolated.
        self.current_frequency = self.frequencies[0] if self.frequencies else 0

        # Per-frequency calibration corrections
        self.freq_cal = {}
        for freq in frequencies:
            self.freq_cal[freq] = FrequencyCalibration(freq, 0.0, 1.0)

    def get_frequencies(self):
        """Get list of valid calibration frequencies."""
        return self.frequencies.copy()

    def set_frequency(self, freq_mhz):
        """
        Set current operating frequency.

        Any frequency inside the calibrated range is accepted; the
        corrections are interpolated between the neighbouring calibration
        points. Outside the range the frequency is clamped to the nearest
        end point.

        Args:
            freq_mhz: Frequency in MHz

        Returns:
            Actual frequency set
        """
        if not self.frequencies:
            return 0

        freq = max(self.frequencies[0], min(self.frequencies[-1], freq_mhz))
        if freq == int(freq):
            freq = int(freq)
        self.current_frequency = freq
        return freq

    def nearest_frequency(self, freq_mhz=None):
        """Calibration point closest to freq_mhz (default: current frequency)."""
        if not self.frequencies:
            return None
        if freq_mhz is None:
            freq_mhz = self.current_frequency
        return min(self.frequencies, key=lambda f: abs(f - freq_mhz))

    def _bracket(self, freq):
        """
        Return (f_lo, f_hi, t) so that freq = f_lo + t * (f_hi - f_lo),
        with f_lo and f_hi adjacent calibration points. At or beyond the
        ends, and at an exact point, f_lo == f_hi and t == 0.
        """
        freqs = self.frequencies
        if freq <= freqs[0]:
            return freqs[0], freqs[0], 0.0
        if freq >= freqs[-1]:
            return freqs[-1], freqs[-1], 0.0
        for i in range(1, len(freqs)):
            if freq <= freqs[i]:
                lo, hi = freqs[i - 1], freqs[i]
                if freq == hi:
                    return hi, hi, 0.0
                return lo, hi, (freq - lo) / (hi - lo)
        return freqs[-1], freqs[-1], 0.0

    def _interpolate(self, freq, getter):
        """Linearly interpolate a per-point value at freq."""
        lo, hi, t = self._bracket(freq)
        v_lo = getter(lo)
        if lo == hi:
            return v_lo
        return v_lo + t * (getter(hi) - v_lo)

    def _point_offset(self, freq):
        cal = self.freq_cal.get(freq)
        return cal.offset if cal else 0.0

    def _point_slope(self, freq):
        cal = self.freq_cal.get(freq)
        return cal.slope if cal else 1.0

    def get_frequency(self):
        """Get current operating frequency."""
        return self.current_frequency

    def set_offset(self, offset, frequency=None):
        """
        Set calibration offset at the calibration point nearest to
        frequency (default: current frequency).

        Returns:
            The calibration frequency the offset was stored at, or None
        """
        point = self.nearest_frequency(frequency)
        if point is None:
            return None
        if point in self.freq_cal:
            self.freq_cal[point].offset = offset
        else:
            self.freq_cal[point] = FrequencyCalibration(point, offset, 1.0)
        return point

    def get_offset(self, frequency=None):
        """Get calibration offset at a frequency, interpolated between points."""
        if not self.frequencies:
            return 0.0
        freq = frequency if frequency is not None else self.current_frequency
        return self._interpolate(freq, self._point_offset)

    def set_slope(self, slope, frequency=None):
        """
        Set calibration slope at the calibration point nearest to
        frequency (default: current frequency).

        Returns:
            The calibration frequency the slope was stored at, or None
        """
        point = self.nearest_frequency(frequency)
        if point is None:
            return None
        if point in self.freq_cal:
            self.freq_cal[point].slope = slope
        else:
            self.freq_cal[point] = FrequencyCalibration(point, 0.0, slope)
        return point

    def get_slope(self, frequency=None):
        """Get calibration slope at a frequency, interpolated between points."""
        if not self.frequencies:
            return 1.0
        freq = frequency if frequency is not None else self.current_frequency
        return self._interpolate(freq, self._point_slope)

    def voltage_to_dbm(self, voltage):
        """
        Convert sensor voltage to power in dBm.

        Args:
            voltage: Sensor output voltage

        Returns:
            Power in dBm
        """
        if abs(self.base_slope) < 0.0001:
            return 0.0

        # Base conversion
        raw_dbm = (voltage / self.base_slope) + self.base_intercept

        # Apply frequency-dependent corrections, interpolated between the
        # calibration points that bracket the operating frequency
        freq_offset = self.get_offset()
        freq_slope = self.get_slope()

        return (raw_dbm * freq_slope) + freq_offset

    def get_cal_data_for_storage(self):
        """Get calibration data in format for EEPROM storage."""
        cal_data = {}
        for freq, cal in self.freq_cal.items():
            if abs(cal.offset) > 0.001 or abs(cal.slope - 1.0) > 0.001:
                cal_data[freq] = {'offset': cal.offset, 'slope': cal.slope}
        return cal_data

    def load_cal_data(self, cal_data):
        """Load calibration data from EEPROM format."""
        for freq, cal in cal_data.items():
            freq_int = int(freq) if isinstance(freq, str) else freq
            if freq_int in self.frequencies:
                self.freq_cal[freq_int] = FrequencyCalibration(
                    freq_int,
                    cal.get('offset', 0.0),
                    cal.get('slope', 1.0)
                )


class CalibrationManager:
    """
    Manages calibration for all channels via the sensor head EEPROMs.

    Every sensor head hangs on its own I2C bus (Pico I2C0 for channel 1,
    I2C1 for channel 2), so all heads can use the same EEPROM address and
    nothing has to be selected before talking to a head.
    """

    def __init__(self, buses, eeprom_address=None):
        """
        Initialize calibration manager.

        Args:
            buses: Dict mapping channel number to the machine.I2C bus that
                   goes to that channel's sensor head, e.g. {1: i2c0, 2: i2c1}
            eeprom_address: Sensor EEPROM address (same for all sensors)
        """
        self.buses = dict(buses)
        self.eeprom_address = eeprom_address or EEPROM_DEFAULT_ADDR

        # Calibration data per channel
        self.sensors = {ch: None for ch in self.buses}  # SensorCalibration per channel

        # One EEPROM driver per channel, bound to that channel's bus
        self._eeproms = {
            ch: SensorEEPROM(bus, self.eeprom_address)
            for ch, bus in self.buses.items()
        }

    def get_bus(self, channel):
        """Get the I2C bus for a channel, or None if the channel does not exist."""
        return self.buses.get(channel)

    def _get_eeprom(self, channel):
        """Get the EEPROM driver for a channel, or None if the channel does not exist."""
        return self._eeproms.get(channel)

    def detect_sensor(self, channel):
        """
        Detect and load sensor on specified channel.

        Args:
            channel: Channel number (1 or 2)

        Returns:
            Sensor type string or None if not detected
        """
        eeprom = self._get_eeprom(channel)
        if eeprom is None:
            return None

        if not eeprom.is_present():
            self.sensors[channel] = None
            return None

        # Read sensor info from EEPROM
        info = eeprom.read_sensor_info()
        if info is None:
            self.sensors[channel] = None
            return None

        # Create calibration object
        self.sensors[channel] = SensorCalibration(
            sensor_type=info['type'],
            serial=info['serial'],
            base_slope=info['slope'],
            base_intercept=info['intercept'],
            frequencies=info['frequencies'],
        )

        # Load per-frequency calibration data
        cal_data = eeprom.read_calibration()
        self.sensors[channel].load_cal_data(cal_data)

        return info['type']

    def detect_all_sensors(self):
        """Detect sensors on all channels."""
        results = {}
        for channel in self.buses:
            sensor_type = self.detect_sensor(channel)
            results[channel] = sensor_type
        return results

    def get_sensor(self, channel):
        """Get sensor calibration for channel."""
        return self.sensors.get(channel)

    def get_sensor_type(self, channel):
        """Get detected sensor type for channel."""
        sensor = self.sensors.get(channel)
        return sensor.sensor_type if sensor else None

    def get_sensor_serial(self, channel):
        """Get sensor serial number for channel."""
        sensor = self.sensors.get(channel)
        return sensor.serial if sensor else None

    def set_frequency(self, channel, freq_mhz):
        """Set operating frequency for channel."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.set_frequency(freq_mhz)
        return None

    def get_frequency(self, channel):
        """Get current frequency for channel."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.get_frequency()
        return None

    def get_frequencies(self, channel):
        """Get list of valid frequencies for channel."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.get_frequencies()
        return []

    def set_offset(self, channel, offset, frequency=None):
        """
        Set calibration offset for channel at the nearest calibration point.

        Returns:
            Calibration frequency the offset was stored at, or None
        """
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.set_offset(offset, frequency)
        return None

    def get_offset(self, channel, frequency=None):
        """Get calibration offset for channel at frequency."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.get_offset(frequency)
        return 0.0

    def set_slope(self, channel, slope, frequency=None):
        """
        Set calibration slope for channel at the nearest calibration point.

        Returns:
            Calibration frequency the slope was stored at, or None
        """
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.set_slope(slope, frequency)
        return None

    def get_slope(self, channel, frequency=None):
        """Get calibration slope for channel at frequency."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.get_slope(frequency)
        return 1.0

    def voltage_to_dbm(self, channel, voltage):
        """Convert voltage to dBm for specified channel."""
        sensor = self.sensors.get(channel)
        if sensor:
            return sensor.voltage_to_dbm(voltage)
        return None

    def save(self, channel=None):
        """
        Save calibration to sensor EEPROM.

        Args:
            channel: Channel number or None for all channels

        Returns:
            True if successful
        """
        channels = [channel] if channel else list(self.buses)
        success = True

        for ch in channels:
            sensor = self.sensors.get(ch)
            if sensor is None:
                continue

            eeprom = self._get_eeprom(ch)
            if eeprom is None:
                success = False
                continue

            try:
                cal_data = sensor.get_cal_data_for_storage()
                eeprom.write_calibration(cal_data)
            except OSError as e:
                print("Error saving calibration for channel {}: {}".format(ch, e))
                success = False

        return success

    def restore_defaults(self, channel):
        """
        Restore default calibration for channel.

        Clears all per-frequency corrections.
        """
        sensor = self.sensors.get(channel)
        if sensor:
            # Reset all frequency calibrations to default
            for freq in sensor.frequencies:
                sensor.freq_cal[freq] = FrequencyCalibration(freq, 0.0, 1.0)
            # Save cleared calibration to EEPROM
            self.save(channel)
            return True
        return False

    def get_nearest_frequency(self, channel):
        """Calibration point nearest to the channel's operating frequency."""
        sensor = self.sensors.get(channel)
        return sensor.nearest_frequency() if sensor else None

    def get_sensor_info(self, channel):
        """Get full sensor information for channel."""
        sensor = self.sensors.get(channel)
        if sensor:
            return {
                'type': sensor.sensor_type,
                'serial': sensor.serial,
                'base_slope': sensor.base_slope,
                'base_intercept': sensor.base_intercept,
                'frequencies': sensor.frequencies,
                'current_frequency': sensor.current_frequency,
                'offset': sensor.get_offset(),
                'slope': sensor.get_slope(),
            }
        return None
