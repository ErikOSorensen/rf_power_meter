# TCA9548A I2C Multiplexer Driver
# Allows selecting one of 8 I2C channels

from micropython import const

# Default I2C address (A0, A1, A2 all to GND)
TCA9548A_DEFAULT_ADDR = const(0x70)


class TCA9548A:
    """TCA9548A 8-channel I2C multiplexer driver."""

    def __init__(self, i2c, address=TCA9548A_DEFAULT_ADDR):
        """
        Initialize TCA9548A multiplexer.

        Args:
            i2c: I2C bus instance
            address: I2C address (0x70-0x77 based on A0-A2 pins)
        """
        self.i2c = i2c
        self.address = address
        self._current_channel = None

        # Verify device is present
        try:
            self.i2c.writeto(self.address, bytes([0x00]))
        except OSError:
            raise RuntimeError("TCA9548A not found at address 0x{:02X}".format(address))

    def select_channel(self, channel):
        """
        Select a single I2C channel.

        Args:
            channel: Channel number (0-7) or None to disable all

        Returns:
            True if successful
        """
        if channel is None:
            # Disable all channels
            self.i2c.writeto(self.address, bytes([0x00]))
            self._current_channel = None
            return True

        if not 0 <= channel <= 7:
            raise ValueError("Channel must be 0-7")

        # Set bit for selected channel
        self.i2c.writeto(self.address, bytes([1 << channel]))
        self._current_channel = channel
        return True

    def get_channel(self):
        """Get currently selected channel."""
        return self._current_channel

    def disable_all(self):
        """Disable all channels."""
        self.select_channel(None)

    def scan_channel(self, channel):
        """
        Scan for devices on a specific channel.

        Args:
            channel: Channel number (0-7)

        Returns:
            List of I2C addresses found on that channel
        """
        self.select_channel(channel)
        # Scan but exclude the multiplexer's own address
        devices = [addr for addr in self.i2c.scan() if addr != self.address]
        return devices

    def scan_all_channels(self):
        """
        Scan all channels for devices.

        Returns:
            Dict mapping channel number to list of addresses
        """
        results = {}
        for ch in range(8):
            devices = self.scan_channel(ch)
            if devices:
                results[ch] = devices
        self.disable_all()
        return results
