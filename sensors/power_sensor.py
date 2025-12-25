# Power Sensor Reading and Management
# Handles ADC reading, averaging, and power calculation

import uasyncio as asyncio
from machine import Pin
from .ads1115 import ADS1115, PGA_4_096V
from .calibration import CalibrationManager
import config

# Power units
UNIT_DBM = "DBM"
UNIT_DBW = "DBW"
UNIT_MW = "MW"
UNIT_W = "W"


def dbm_to_mw(dbm):
    """Convert dBm to milliwatts."""
    return 10.0 ** (dbm / 10.0)


def dbm_to_w(dbm):
    """Convert dBm to watts."""
    return 10.0 ** ((dbm - 30.0) / 10.0)


def dbm_to_dbw(dbm):
    """Convert dBm to dBW."""
    return dbm - 30.0


class PowerChannel:
    """Represents a single power measurement channel."""

    def __init__(self, channel_num, adc, calibration_mgr):
        """
        Initialize power channel.

        Args:
            channel_num: Channel number (1 or 2)
            adc: ADS1115 instance for this channel
            calibration_mgr: CalibrationManager instance
        """
        self.channel_num = channel_num
        self.adc = adc
        self.cal_mgr = calibration_mgr
        self.averaging = config.ADC_SAMPLES_DEFAULT
        self.unit = UNIT_DBM

        # External attenuator offset (dB, added to measured power)
        self.attenuator = 0.0

        # Current readings
        self.power_voltage = 0.0
        self.power_dbm = None

        # Averaging buffer
        self._samples = []

    @property
    def sensor_type(self):
        """Get detected sensor type."""
        return self.cal_mgr.get_sensor_type(self.channel_num)

    @property
    def sensor_serial(self):
        """Get sensor serial number."""
        return self.cal_mgr.get_sensor_serial(self.channel_num)

    def get_frequency(self):
        """Get current operating frequency in MHz."""
        return self.cal_mgr.get_frequency(self.channel_num)

    def set_frequency(self, freq_mhz):
        """
        Set operating frequency in MHz.

        Args:
            freq_mhz: Frequency in MHz

        Returns:
            Actual frequency set (may snap to nearest valid)
        """
        return self.cal_mgr.set_frequency(self.channel_num, freq_mhz)

    def get_frequencies(self):
        """Get list of valid calibration frequencies for this sensor."""
        return self.cal_mgr.get_frequencies(self.channel_num)

    def read_voltage(self):
        """Read power sensor voltage from ADC."""
        self.power_voltage = self.adc.read_power_voltage()
        return self.power_voltage

    def read_power(self):
        """
        Read and calculate power with averaging.

        Returns:
            Power in dBm or None if sensor not detected
        """
        # Read voltage
        self.power_voltage = self.adc.read_power_voltage()

        # Update averaging buffer
        self._samples.append(self.power_voltage)
        if len(self._samples) > self.averaging:
            self._samples.pop(0)

        # Calculate average voltage
        avg_voltage = sum(self._samples) / len(self._samples)

        # Convert to dBm
        self.power_dbm = self.cal_mgr.voltage_to_dbm(
            self.channel_num, avg_voltage
        )
        return self.power_dbm

    def get_power(self, unit=None, include_attenuator=True):
        """
        Get power in specified unit.

        Args:
            unit: Power unit (DBM, DBW, MW, W) or None for channel default
            include_attenuator: If True, add attenuator offset to reading

        Returns:
            Tuple of (value, unit_string) or (None, unit) if no reading
        """
        if self.power_dbm is None:
            return None, unit or self.unit

        # Apply attenuator offset (add dB to get input power)
        corrected_dbm = self.power_dbm
        if include_attenuator:
            corrected_dbm += self.attenuator

        target_unit = unit or self.unit

        if target_unit == UNIT_DBM:
            return corrected_dbm, "dBm"
        elif target_unit == UNIT_DBW:
            return dbm_to_dbw(corrected_dbm), "dBW"
        elif target_unit == UNIT_MW:
            return dbm_to_mw(corrected_dbm), "mW"
        elif target_unit == UNIT_W:
            return dbm_to_w(corrected_dbm), "W"
        else:
            return corrected_dbm, "dBm"

    def set_averaging(self, samples):
        """Set number of samples for averaging."""
        self.averaging = max(1, min(256, samples))
        self._samples = []  # Clear buffer on change

    def set_unit(self, unit):
        """Set default power unit."""
        if unit in [UNIT_DBM, UNIT_DBW, UNIT_MW, UNIT_W]:
            self.unit = unit

    def clear_averaging(self):
        """Clear averaging buffer."""
        self._samples = []

    def set_attenuator(self, value_db):
        """
        Set external attenuator value.

        Args:
            value_db: Attenuator value in dB (positive number)
                      This is added to measured power to get input power.
                      Example: 40 dB attenuator, sensor reads -10 dBm,
                               reported power is +30 dBm.
        """
        self.attenuator = float(value_db)

    def get_attenuator(self):
        """Get current attenuator value in dB."""
        return self.attenuator


class PowerMeter:
    """Dual-channel RF power meter."""

    def __init__(self, i2c):
        """
        Initialize power meter.

        Args:
            i2c: I2C bus instance
        """
        self.i2c = i2c
        self.cal_mgr = CalibrationManager(i2c)

        # Initialize ADCs
        self.adc1 = ADS1115(i2c, config.ADS1115_ADDR_CH1, gain=PGA_4_096V)
        self.adc2 = ADS1115(i2c, config.ADS1115_ADDR_CH2, gain=PGA_4_096V)

        # Initialize channels
        self.channels = {
            1: PowerChannel(1, self.adc1, self.cal_mgr),
            2: PowerChannel(2, self.adc2, self.cal_mgr),
        }

        # Measurement state
        self.running = False
        self._task = None

        # Hot-swap detection state (pending re-detection flags)
        self._detect_pending = {1: False, 2: False}

        # Initialize presence detect pins with pull-down and IRQ
        self._detect_pins = {}
        self._setup_presence_detect()

    def _setup_presence_detect(self):
        """Set up GPIO pins for sensor presence detection."""
        pin_map = {
            1: config.DETECT_PIN_CH1,
            2: config.DETECT_PIN_CH2,
        }

        for channel, pin_num in pin_map.items():
            pin = Pin(pin_num, Pin.IN, Pin.PULL_DOWN)
            self._detect_pins[channel] = pin

            # Create closure to capture channel number
            def make_handler(ch):
                def handler(p):
                    self._on_presence_change(ch, p.value())
                return handler

            pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
                    handler=make_handler(channel))

    def _on_presence_change(self, channel, present):
        """
        Handle sensor presence change (called from IRQ context).

        Args:
            channel: Channel number (1 or 2)
            present: True if sensor connected, False if disconnected
        """
        # Set flag for main loop to handle (avoid I2C in IRQ context)
        self._detect_pending[channel] = True

    def check_presence_changes(self):
        """
        Check for pending presence changes and re-detect sensors.

        Call this periodically from the main loop.

        Returns:
            Dict of channels that changed: {channel: sensor_type or None}
        """
        changes = {}

        for channel in [1, 2]:
            if self._detect_pending[channel]:
                self._detect_pending[channel] = False

                # Check current presence state
                present = self._detect_pins[channel].value()

                if present:
                    # Sensor connected - detect and load calibration
                    sensor_type = self.cal_mgr.detect_sensor(channel)
                    self.channels[channel].clear_averaging()
                    changes[channel] = sensor_type
                    print("Sensor {} connected: {}".format(
                        channel, sensor_type or "unknown"))
                else:
                    # Sensor disconnected - clear calibration data
                    self.cal_mgr.sensors[channel] = None
                    self.channels[channel].clear_averaging()
                    self.channels[channel].power_dbm = None
                    changes[channel] = None
                    print("Sensor {} disconnected".format(channel))

        return changes

    def is_sensor_present(self, channel):
        """Check if sensor is physically present on channel."""
        if channel in self._detect_pins:
            return bool(self._detect_pins[channel].value())
        return False

    def detect_sensors(self):
        """
        Detect sensors on all channels.

        Returns:
            Dict mapping channel to sensor type (or None)
        """
        return self.cal_mgr.detect_all_sensors()

    def get_channel(self, channel_num):
        """Get channel by number."""
        return self.channels.get(channel_num)

    def read_all(self):
        """Read all channels once."""
        results = {}
        for ch_num, channel in self.channels.items():
            power = channel.read_power()
            results[ch_num] = {
                "power_dbm": power,
                "sensor_type": channel.sensor_type,
                "voltage": channel.power_voltage,
            }
        return results

    async def read_task(self, interval_ms=None):
        """
        Async task for continuous reading.

        Args:
            interval_ms: Reading interval in milliseconds
        """
        if interval_ms is None:
            interval_ms = config.SENSOR_READ_MS

        self.running = True

        while self.running:
            for channel in self.channels.values():
                channel.read_power()

            await asyncio.sleep_ms(interval_ms)

    def start(self, interval_ms=None):
        """Start continuous reading task."""
        if self._task is None:
            self._task = asyncio.create_task(self.read_task(interval_ms))
        return self._task

    def stop(self):
        """Stop continuous reading task."""
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None

    def save_calibration(self, channel=None):
        """Save calibration to sensor EEPROM."""
        return self.cal_mgr.save(channel)

    def restore_calibration(self, channel):
        """Restore default calibration for channel."""
        return self.cal_mgr.restore_defaults(channel)

    def set_cal_offset(self, channel, offset):
        """Set calibration offset for channel at current frequency."""
        self.cal_mgr.set_offset(channel, offset)

    def set_cal_slope(self, channel, slope):
        """Set calibration slope for channel at current frequency."""
        self.cal_mgr.set_slope(channel, slope)

    def set_frequency(self, channel, freq_mhz):
        """Set operating frequency for channel."""
        return self.cal_mgr.set_frequency(channel, freq_mhz)

    def get_frequency(self, channel):
        """Get current frequency for channel in MHz."""
        return self.cal_mgr.get_frequency(channel)

    def get_frequencies(self, channel):
        """Get list of valid calibration frequencies for channel."""
        return self.cal_mgr.get_frequencies(channel)

    def reset(self):
        """Reset meter to default state (including frequency to lowest)."""
        for ch_num, channel in self.channels.items():
            channel.set_averaging(config.ADC_SAMPLES_DEFAULT)
            channel.set_unit(UNIT_DBM)
            channel.clear_averaging()
            channel.set_attenuator(0.0)  # Clear external attenuator
            # Reset frequency to lowest for sensor
            freqs = self.cal_mgr.get_frequencies(ch_num)
            if freqs:
                self.cal_mgr.set_frequency(ch_num, freqs[0])
