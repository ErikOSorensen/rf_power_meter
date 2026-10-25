# RF Power Meter Configuration
# Hardware pin assignments and system defaults

from micropython import const

# === SPI0: W5500 Ethernet ===
W5500_SPI_ID = const(0)
W5500_SCK = const(18)
W5500_MOSI = const(19)
W5500_MISO = const(16)
W5500_CS = const(17)
W5500_RST = const(20)

# === SPI1: SSD1322 OLED display (4-wire SPI, write only) ===
DISPLAY_SPI_ID = const(1)
DISPLAY_SCK = const(10)      # GP10 - SPI1 SCK
DISPLAY_MOSI = const(11)     # GP11 - SPI1 TX
DISPLAY_CS = const(13)       # GP13 - chip select (active low)
DISPLAY_DC = const(14)       # GP14 - data/command (high = data)
DISPLAY_RST = const(15)      # GP15 - reset (active low)
DISPLAY_SPI_BAUD = const(10_000_000)

# === I2C: one hardware controller per sensor head ===
# Each head has its own bus, so all heads can carry identical I2C
# addresses and no multiplexer is needed.
I2C_FREQ = const(400000)

I2C_CH1_ID = const(0)        # Pico I2C0 -> sensor head 1
I2C_CH1_SDA = const(0)       # GP0
I2C_CH1_SCL = const(1)       # GP1

I2C_CH2_ID = const(1)        # Pico I2C1 -> sensor head 2
I2C_CH2_SDA = const(2)       # GP2
I2C_CH2_SCL = const(3)       # GP3

# === Sensor Presence Detect Pins ===
# Active low: the head ties the line to GND, the main unit pulls it up.
DETECT_PIN_CH1 = const(4)    # GP4 - Sensor 1 presence detect
DETECT_PIN_CH2 = const(5)    # GP5 - Sensor 2 presence detect

# === Rotary Encoder with Push Switch (front panel) ===
# Contacts go through RC filters and a 74HC14 Schmitt inverter, so the
# Pico sees clean, inverted edges: a closed contact reads HIGH.
ENCODER_A = const(6)         # GP6 - quadrature A (via 74HC14)
ENCODER_B = const(7)         # GP7 - quadrature B (via 74HC14)
ENCODER_SW = const(8)        # GP8 - push switch (via 74HC14)
ENCODER_SW_ACTIVE_HIGH = True   # True with the 74HC14 inverter
ENCODER_REVERSE = False      # Flip if clockwise decreases values
ENCODER_STEPS_PER_DETENT = const(4)  # Quadrature transitions per click (24 PPR / 24 detent)

# === Front Panel UI ===
UI_POLL_MS = const(20)           # Front panel poll interval
UI_EDIT_TIMEOUT_MS = const(5000) # Return to measurement view after idle
UI_ATTEN_STEP_DB = const(1)      # Attenuator step per encoder click
UI_ATTEN_MAX_DB = const(60)      # Attenuator ceiling for manual entry

# === I2C Addresses (identical in every sensor head) ===
EEPROM_ADDRESS = const(0x50)       # AT24C02 / AT24CS04
ADS1115_ADDRESS = const(0x48)      # ADS1115 (ADDR pin to GND)
TEMP_SENSOR_ADDRESS = const(0x18)  # MCP9808 (A0-A2 to GND)

# === Network Configuration ===
SCPI_PORT = const(5025)
MDNS_HOSTNAME = "rfmeter"
USE_DHCP = True

# === ADC Configuration ===
ADC_SAMPLES_DEFAULT = const(16)  # Default averaging count
ADC_SAMPLE_RATE = const(128)     # Samples per second (8, 16, 32, 64, 128, 250, 475, 860)

# === Display Configuration ===
DISPLAY_WIDTH = const(256)
DISPLAY_HEIGHT = const(64)
DISPLAY_COL_OFFSET = const(0x1C)  # First RAM column of a 256-wide panel (module dependent)
DISPLAY_CONTRAST = const(0x9F)    # SSD1322 contrast current, 0x00-0xFF
DISPLAY_UPDATE_MS = const(200)    # 5 Hz update rate

# === Sensor Reading Configuration ===
SENSOR_READ_MS = const(50)       # 20 Hz reading rate
TEMP_READ_EVERY = const(20)      # Read head temperature every N power readings (1 Hz)

# === Instrument Identity ===
MANUFACTURER = "HomeLab"
MODEL = "RFPM-2CH"
SERIAL = "001"
VERSION = "1.0.0"
SCPI_VERSION = "1999.0"

# Note: Calibration data is stored on sensor module EEPROMs, not in flash
