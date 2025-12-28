# RF Power Meter Configuration
# Hardware pin assignments and system defaults

from micropython import const

# === SPI Pins for W5500 Ethernet ===
W5500_SPI_ID = const(0)
W5500_SCK = const(18)
W5500_MOSI = const(19)
W5500_MISO = const(16)
W5500_CS = const(17)
W5500_RST = const(20)

# === I2C Pins ===
I2C_ID = const(0)
I2C_SDA = const(0)
I2C_SCL = const(1)
I2C_FREQ = const(400000)

# === Sensor Presence Detect Pins ===
DETECT_PIN_CH1 = const(2)  # GP2 - Sensor 1 presence detect
DETECT_PIN_CH2 = const(3)  # GP3 - Sensor 2 presence detect

# === I2C Multiplexer Reset Pin ===
MUX_RESET_PIN = const(4)   # GP4 - TCA9548A reset (active low, optional)

# === I2C Addresses ===
ADS1115_ADDR_CH1 = const(0x48)  # ADDR pin to GND
ADS1115_ADDR_CH2 = const(0x49)  # ADDR pin to VDD
OLED_ADDR_CH1 = const(0x3C)
OLED_ADDR_CH2 = const(0x3D)

# === I2C Multiplexer for Sensor EEPROMs ===
MUX_ADDRESS = const(0x70)       # TCA9548A address (A0-A2 to GND)
MUX_CHANNEL_1 = const(0)        # Mux channel for sensor 1 EEPROM
MUX_CHANNEL_2 = const(1)        # Mux channel for sensor 2 EEPROM
EEPROM_ADDRESS = const(0x50)    # All sensor EEPROMs at same address

# === Network Configuration ===
SCPI_PORT = const(5025)
MDNS_HOSTNAME = "rfmeter"
USE_DHCP = True

# === ADC Configuration ===
ADC_SAMPLES_DEFAULT = const(16)  # Default averaging count
ADC_SAMPLE_RATE = const(128)     # Samples per second (8, 16, 32, 64, 128, 250, 475, 860)

# === Display Configuration ===
DISPLAY_WIDTH = const(128)
DISPLAY_HEIGHT = const(64)
DISPLAY_UPDATE_MS = const(200)   # 5 Hz update rate

# === Sensor Reading Configuration ===
SENSOR_READ_MS = const(50)       # 20 Hz reading rate

# === Instrument Identity ===
MANUFACTURER = "HomeLab"
MODEL = "RFPM-2CH"
SERIAL = "001"
VERSION = "1.0.0"
SCPI_VERSION = "1999.0"

# Note: Calibration data is stored on sensor module EEPROMs, not in flash
