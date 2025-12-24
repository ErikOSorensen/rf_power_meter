# W5500 Ethernet Initialization
# Configures SPI and network interface

from machine import Pin, SPI
import network
import time
import config


class W5500Network:
    """Manages W5500 Ethernet connection."""

    def __init__(self):
        """Initialize W5500 network interface."""
        self.spi = None
        self.nic = None
        self.ip_address = None
        self.mac_address = None

    def init(self):
        """
        Initialize SPI and W5500.

        Returns:
            True if successful
        """
        # Initialize SPI
        self.spi = SPI(
            config.W5500_SPI_ID,
            baudrate=10_000_000,
            polarity=0,
            phase=0,
            sck=Pin(config.W5500_SCK),
            mosi=Pin(config.W5500_MOSI),
            miso=Pin(config.W5500_MISO),
        )

        # Reset W5500
        rst = Pin(config.W5500_RST, Pin.OUT)
        rst.value(0)
        time.sleep_ms(100)
        rst.value(1)
        time.sleep_ms(100)

        # Initialize network interface
        cs = Pin(config.W5500_CS, Pin.OUT)
        self.nic = network.WIZNET5K(self.spi, cs, rst)

        # Get MAC address
        self.mac_address = self._format_mac(self.nic.config('mac'))

        return True

    def connect(self, use_dhcp=True, static_ip=None, timeout_ms=10000):
        """
        Connect to network.

        Args:
            use_dhcp: Use DHCP for IP configuration
            static_ip: Static IP tuple (ip, subnet, gateway, dns) if not using DHCP
            timeout_ms: Connection timeout in milliseconds

        Returns:
            IP address string or None if failed
        """
        if self.nic is None:
            return None

        try:
            # Activate interface
            self.nic.active(True)

            if use_dhcp:
                # Configure for DHCP
                self.nic.ifconfig('dhcp')

                # Wait for DHCP
                start = time.ticks_ms()
                while not self.nic.isconnected():
                    if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                        return None
                    time.sleep_ms(100)
            else:
                # Static IP configuration
                if static_ip:
                    self.nic.ifconfig(static_ip)

            # Get assigned IP
            ifconfig = self.nic.ifconfig()
            self.ip_address = ifconfig[0]
            return self.ip_address

        except Exception as e:
            print("Network error:", e)
            return None

    def disconnect(self):
        """Disconnect from network."""
        if self.nic:
            self.nic.active(False)
            self.ip_address = None

    def is_connected(self):
        """Check if connected."""
        if self.nic:
            return self.nic.isconnected()
        return False

    def get_ip(self):
        """Get current IP address."""
        return self.ip_address

    def get_mac(self):
        """Get MAC address."""
        return self.mac_address

    def get_ifconfig(self):
        """Get full interface configuration."""
        if self.nic:
            return self.nic.ifconfig()
        return None

    def _format_mac(self, mac_bytes):
        """Format MAC address bytes as string."""
        return ':'.join('{:02X}'.format(b) for b in mac_bytes)


# Singleton instance
_network = None


def get_network():
    """Get network singleton."""
    global _network
    if _network is None:
        _network = W5500Network()
    return _network


async def init_network_async(use_dhcp=True, timeout_ms=10000):
    """
    Initialize network asynchronously.

    Args:
        use_dhcp: Use DHCP
        timeout_ms: Timeout for DHCP

    Returns:
        IP address or None
    """
    import uasyncio as asyncio

    net = get_network()
    net.init()

    if use_dhcp:
        net.nic.active(True)
        net.nic.ifconfig('dhcp')

        start = time.ticks_ms()
        while not net.nic.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                return None
            await asyncio.sleep_ms(100)

        ifconfig = net.nic.ifconfig()
        net.ip_address = ifconfig[0]
        return net.ip_address

    return net.connect(use_dhcp=False)
