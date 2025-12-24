# SCPI Command Implementations
# Defines all supported SCPI commands for the RF power meter

from .parser import SCPIParser
from sensors.power_sensor import UNIT_DBM, UNIT_DBW, UNIT_MW, UNIT_W
import config


class SCPICommandHandler:
    """Handles SCPI commands for the RF power meter."""

    def __init__(self, power_meter, network=None):
        """
        Initialize command handler.

        Args:
            power_meter: PowerMeter instance
            network: W5500Network instance (optional)
        """
        self.meter = power_meter
        self.network = network
        self.parser = SCPIParser()
        self.opc_flag = True  # Operation complete

        self._register_commands()

    def _register_commands(self):
        """Register all SCPI commands."""
        p = self.parser

        # IEEE 488.2 Common Commands
        p.register("*IDN", self._cmd_idn, self._query_idn)
        p.register("*RST", self._cmd_rst, self._cmd_rst)
        p.register("*OPC", self._cmd_opc, self._query_opc)
        p.register("*CLS", self._cmd_cls, self._cmd_cls)

        # Measurement Commands
        p.register("MEASure:POWer", self._cmd_measure, self._query_power)
        p.register("MEASure:POWer:UNIT", self._cmd_unit, self._query_unit)
        p.register("MEASure:POWer:AVERage", self._cmd_average, self._query_average)
        p.register("MEASure:VOLTage", self._cmd_measure, self._query_voltage)

        # Frequency Commands
        p.register("SENSe:FREQuency", self._cmd_frequency, self._query_frequency)
        p.register("SENSe:FREQuency:CATalog", self._query_freq_catalog, self._query_freq_catalog)

        # Attenuator Commands
        p.register("SENSe:ATTenuation", self._cmd_attenuator, self._query_attenuator)

        # Calibration Commands
        p.register("CALibrate:POWer:OFFSet", self._cmd_cal_offset, self._query_cal_offset)
        p.register("CALibrate:POWer:SLOPe", self._cmd_cal_slope, self._query_cal_slope)
        p.register("CALibrate:POWer:SAVE", self._cmd_cal_save, self._cmd_cal_save)
        p.register("CALibrate:POWer:RESTore", self._cmd_cal_restore, self._cmd_cal_restore)
        p.register("CALibrate:SENSor:TYPE", self._cmd_sensor_type, self._query_sensor_type)

        # System Commands
        p.register("SYSTem:ERRor", self._query_error, self._query_error)
        p.register("SYSTem:VERSion", self._query_version, self._query_version)
        p.register("SYSTem:NET:IP", self._query_ip, self._query_ip)
        p.register("SYSTem:NET:MAC", self._query_mac, self._query_mac)

    def handle(self, command_str):
        """
        Handle SCPI command string.

        Args:
            command_str: Raw SCPI command

        Returns:
            Response string or None
        """
        return self.parser.execute(command_str)

    def _get_channel(self, cmd, default=1):
        """Get channel number from command."""
        return cmd.channel if cmd.channel else default

    # === IEEE 488.2 Common Commands ===

    def _cmd_idn(self, cmd):
        """*IDN - no action for command form."""
        return None

    def _query_idn(self, cmd):
        """*IDN? - Return instrument identification."""
        return "{},{},{},{}".format(
            config.MANUFACTURER,
            config.MODEL,
            config.SERIAL,
            config.VERSION
        )

    def _cmd_rst(self, cmd):
        """*RST - Reset instrument to default state."""
        self.meter.reset()
        self.parser.clear_errors()
        return None

    def _cmd_opc(self, cmd):
        """*OPC - Set operation complete flag."""
        self.opc_flag = True
        return None

    def _query_opc(self, cmd):
        """*OPC? - Query operation complete."""
        return "1" if self.opc_flag else "0"

    def _cmd_cls(self, cmd):
        """*CLS - Clear status."""
        self.parser.clear_errors()
        return None

    # === Measurement Commands ===

    def _cmd_measure(self, cmd):
        """MEASure command - trigger measurement."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)
        if channel:
            channel.read_power()
        return None

    def _query_power(self, cmd):
        """MEASure:POWer? - Query power reading."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            self.parser.add_error(-200, "Invalid channel")
            return None

        if channel.sensor_type is None:
            self.parser.add_error(-230, "No sensor detected")
            return "9.91E37"  # SCPI "not a number"

        power, unit = channel.get_power()
        if power is None:
            return "9.91E37"

        return "{:.3f}".format(power)

    def _query_voltage(self, cmd):
        """MEASure:VOLTage? - Query raw voltage."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return None

        return "{:.6f}".format(channel.power_voltage)

    def _cmd_unit(self, cmd):
        """MEASure:POWer:UNIT - Set power unit."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return None

        unit_str = cmd.get_param_str("DBM").upper()
        unit_map = {
            "DBM": UNIT_DBM,
            "DBW": UNIT_DBW,
            "MW": UNIT_MW,
            "W": UNIT_W,
        }

        if unit_str in unit_map:
            channel.set_unit(unit_map[unit_str])
        else:
            self.parser.add_error(-100, "Invalid unit")

        return None

    def _query_unit(self, cmd):
        """MEASure:POWer:UNIT? - Query power unit."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return None

        return channel.unit

    def _cmd_average(self, cmd):
        """MEASure:POWer:AVERage - Set averaging count."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return None

        count = cmd.get_param_int(16)
        channel.set_averaging(count)
        return None

    def _query_average(self, cmd):
        """MEASure:POWer:AVERage? - Query averaging count."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return None

        return str(channel.averaging)

    # === Frequency Commands ===

    def _cmd_frequency(self, cmd):
        """SENSe:FREQuency - Set operating frequency in MHz."""
        ch = self._get_channel(cmd)
        freq = cmd.get_param_float()

        if freq is None:
            self.parser.add_error(-100, "Missing frequency parameter")
            return None

        channel = self.meter.get_channel(ch)
        if channel is None:
            self.parser.add_error(-200, "Invalid channel")
            return None

        if channel.sensor_type is None:
            self.parser.add_error(-230, "No sensor detected")
            return None

        # Set frequency (snaps to nearest valid)
        actual_freq = self.meter.set_frequency(ch, int(freq))

        if actual_freq != int(freq):
            # Frequency was snapped to nearest valid value
            self.parser.add_error(-100, "Frequency snapped to {}".format(actual_freq))

        return None

    def _query_frequency(self, cmd):
        """SENSe:FREQuency? - Query current operating frequency in MHz."""
        ch = self._get_channel(cmd)
        freq = self.meter.get_frequency(ch)

        if freq is None:
            return "0"

        return str(freq)

    def _query_freq_catalog(self, cmd):
        """SENSe:FREQuency:CATalog? - Query available calibration frequencies."""
        ch = self._get_channel(cmd)
        freqs = self.meter.get_frequencies(ch)

        if not freqs:
            return ""

        # Return comma-separated list
        return ",".join(str(f) for f in freqs)

    # === Attenuator Commands ===

    def _cmd_attenuator(self, cmd):
        """SENSe:ATTenuation - Set external attenuator value in dB.

        Example: SENS1:ATT 40 sets a 40 dB attenuator on channel 1.
        The meter will add this value to measured power when reporting.
        """
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            self.parser.add_error(-200, "Invalid channel")
            return None

        atten = cmd.get_param_float(0.0)
        channel.set_attenuator(atten)
        return None

    def _query_attenuator(self, cmd):
        """SENSe:ATTenuation? - Query external attenuator value in dB."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return "0"

        return "{:.1f}".format(channel.get_attenuator())

    # === Calibration Commands ===

    def _cmd_cal_offset(self, cmd):
        """CALibrate:POWer:OFFSet - Set calibration offset for current frequency."""
        ch = self._get_channel(cmd)
        offset = cmd.get_param_float(0.0)
        self.meter.set_cal_offset(ch, offset)  # Uses current frequency
        return None

    def _query_cal_offset(self, cmd):
        """CALibrate:POWer:OFFSet? - Query calibration offset for current frequency."""
        ch = self._get_channel(cmd)
        offset = self.meter.cal_mgr.get_offset(ch)  # Uses current frequency
        return "{:.3f}".format(offset)

    def _cmd_cal_slope(self, cmd):
        """CALibrate:POWer:SLOPe - Set calibration slope for current frequency."""
        ch = self._get_channel(cmd)
        slope = cmd.get_param_float(1.0)
        self.meter.set_cal_slope(ch, slope)  # Uses current frequency
        return None

    def _query_cal_slope(self, cmd):
        """CALibrate:POWer:SLOPe? - Query calibration slope for current frequency."""
        ch = self._get_channel(cmd)
        slope = self.meter.cal_mgr.get_slope(ch)  # Uses current frequency
        return "{:.6f}".format(slope)

    def _cmd_cal_save(self, cmd):
        """CALibrate:POWer:SAVE - Save calibration to flash."""
        if self.meter.save_calibration():
            return None
        else:
            self.parser.add_error(-300, "Calibration save failed")
            return None

    def _cmd_cal_restore(self, cmd):
        """CALibrate:POWer:RESTore - Restore default calibration."""
        ch = self._get_channel(cmd)
        self.meter.restore_calibration(ch)
        return None

    def _cmd_sensor_type(self, cmd):
        """CALibrate:SENSor:TYPE - no action."""
        return None

    def _query_sensor_type(self, cmd):
        """CALibrate:SENSor:TYPE? - Query detected sensor type."""
        ch = self._get_channel(cmd)
        channel = self.meter.get_channel(ch)

        if channel is None:
            return "NONE"

        return channel.sensor_type or "NONE"

    # === System Commands ===

    def _query_error(self, cmd):
        """SYSTem:ERRor? - Get error from queue."""
        return self.parser.get_error()

    def _query_version(self, cmd):
        """SYSTem:VERSion? - Query SCPI version."""
        return config.SCPI_VERSION

    def _query_ip(self, cmd):
        """SYSTem:NET:IP? - Query IP address."""
        if self.network:
            ip = self.network.get_ip()
            return ip if ip else "0.0.0.0"
        return "0.0.0.0"

    def _query_mac(self, cmd):
        """SYSTem:NET:MAC? - Query MAC address."""
        if self.network:
            mac = self.network.get_mac()
            return mac if mac else "00:00:00:00:00:00"
        return "00:00:00:00:00:00"


def create_scpi_handler(power_meter, network=None):
    """
    Create SCPI command handler function.

    Args:
        power_meter: PowerMeter instance
        network: W5500Network instance

    Returns:
        Handler function for SCPI commands
    """
    handler = SCPICommandHandler(power_meter, network)
    return handler.handle
