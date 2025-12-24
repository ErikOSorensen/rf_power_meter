# RF Power Meter - Main Entry Point
# Dual-channel RF power meter with SCPI interface

import uasyncio as asyncio
from machine import I2C, Pin
import time

import config
from sensors.power_sensor import PowerMeter
from display.power_display import DisplayManager
from network.w5500 import get_network, init_network_async
from network.tcp_server import TCPServer
from network.mdns import MDNSResponder
from scpi.commands import create_scpi_handler


class RFPowerMeter:
    """Main RF Power Meter application."""

    def __init__(self):
        """Initialize power meter components."""
        self.i2c = None
        self.meter = None
        self.display_mgr = None
        self.network = None
        self.tcp_server = None
        self.mdns = None
        self.scpi_handler = None
        self.running = False

    def init_hardware(self):
        """Initialize I2C bus and hardware."""
        print("Initializing hardware...")

        # Initialize I2C bus
        self.i2c = I2C(
            config.I2C_ID,
            sda=Pin(config.I2C_SDA),
            scl=Pin(config.I2C_SCL),
            freq=config.I2C_FREQ
        )

        # Scan I2C bus
        devices = self.i2c.scan()
        print("I2C devices found:", [hex(d) for d in devices])

        # Initialize power meter
        self.meter = PowerMeter(self.i2c)
        print("Power meter initialized")

        # Detect sensors via EEPROM
        print("Detecting sensors...")
        sensors = self.meter.detect_sensors()
        for ch, sensor_type in sensors.items():
            if sensor_type:
                serial = self.meter.cal_mgr.get_sensor_serial(ch)
                print("  Channel {}: {} (S/N: {})".format(ch, sensor_type, serial))
            else:
                print("  Channel {}: No sensor".format(ch))

        # Initialize displays
        self.display_mgr = DisplayManager(self.i2c)
        self.display_mgr.show_startup()
        print("Displays initialized")

        time.sleep(1)  # Show startup screen briefly

    async def init_network(self):
        """Initialize network connection."""
        print("Initializing network...")

        self.network = get_network()
        self.network.init()

        # Show DHCP status on displays
        self.display_mgr.set_ip_address(None)

        # Connect with DHCP
        ip = await init_network_async(use_dhcp=config.USE_DHCP)

        if ip:
            print("Network connected: {}".format(ip))
            self.display_mgr.set_ip_address(ip)

            # Initialize mDNS
            self.mdns = MDNSResponder(config.MDNS_HOSTNAME, ip)
            print("mDNS hostname: {}.local".format(config.MDNS_HOSTNAME))
        else:
            print("Network connection failed")
            self.display_mgr.show_error("Network failed")

        return ip

    def init_scpi(self):
        """Initialize SCPI command handler."""
        self.scpi_handler = create_scpi_handler(self.meter, self.network)
        print("SCPI handler initialized")

    async def sensor_task(self):
        """Task for continuous sensor reading."""
        print("Sensor task started")

        while self.running:
            try:
                for channel in self.meter.channels.values():
                    channel.read_power()

                await asyncio.sleep_ms(config.SENSOR_READ_MS)

            except Exception as e:
                print("Sensor task error:", e)
                await asyncio.sleep_ms(1000)

    async def display_task(self):
        """Task for display updates."""
        print("Display task started")

        while self.running:
            try:
                self.display_mgr.update_all(self.meter)
                await asyncio.sleep_ms(config.DISPLAY_UPDATE_MS)

            except Exception as e:
                print("Display task error:", e)
                await asyncio.sleep_ms(1000)

    async def scpi_server_task(self):
        """Task for SCPI TCP server."""
        if self.network.get_ip() is None:
            print("SCPI server: No network")
            return

        print("Starting SCPI server on port {}".format(config.SCPI_PORT))
        self.tcp_server = TCPServer(self.scpi_handler, config.SCPI_PORT)
        await self.tcp_server.start()

        # Keep running while active
        while self.running:
            await asyncio.sleep_ms(1000)

    async def mdns_task(self):
        """Task for mDNS responder."""
        if self.mdns is None:
            print("mDNS: Not configured")
            return

        # Send initial announcement
        await asyncio.sleep_ms(100)
        self.mdns.announce()

        # Run responder
        await self.mdns.run()

    async def main(self):
        """Main async entry point."""
        print("\n=== RF Power Meter ===")
        print("Model: {} v{}".format(config.MODEL, config.VERSION))
        print()

        # Initialize hardware
        self.init_hardware()

        # Initialize network
        await self.init_network()

        # Initialize SCPI
        self.init_scpi()

        # Start all tasks
        self.running = True

        tasks = [
            asyncio.create_task(self.sensor_task()),
            asyncio.create_task(self.display_task()),
        ]

        # Add network tasks if connected
        if self.network and self.network.get_ip():
            tasks.append(asyncio.create_task(self.scpi_server_task()))
            if self.mdns:
                tasks.append(asyncio.create_task(self.mdns_task()))

        print("\nSystem ready")
        print("SCPI: {}:{}".format(
            self.network.get_ip() if self.network else "N/A",
            config.SCPI_PORT
        ))
        print()

        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    def run(self):
        """Run the power meter."""
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.running = False


# Entry point
def main():
    """Application entry point."""
    app = RFPowerMeter()
    app.run()


if __name__ == "__main__":
    main()
