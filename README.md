# RF Power Meter

Dual-channel RF power meter using Raspberry Pi Pico with W5500 Ethernet, featuring SCPI control and mDNS discovery.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                    (Application Controller)                      │
│  - Initializes all subsystems                                   │
│  - Runs async task scheduler                                    │
│  - Coordinates sensor reading, display, and network tasks       │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   sensors/  │ │  display/   │ │  network/   │ │    scpi/    │
│             │ │             │ │             │ │             │
│ ADC reading │ │ OLED output │ │ Ethernet &  │ │  Command    │
│ EEPROM cal  │ │ Power bars  │ │ TCP server  │ │  parsing    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

## Key Features

- **EEPROM-based calibration**: Each sensor module stores its own calibration data in an onboard EEPROM. Calibration travels with the sensor, not the channel.
- **Frequency-dependent calibration**: Store separate offset/slope corrections for each calibration frequency.
- **Hot-swappable sensors**: Sensors are automatically detected at startup via I2C multiplexer.
- **SCPI control**: Standard SCPI commands over TCP port 5025.
- **mDNS discovery**: Find the meter as `rfmeter.local`.

## File Responsibilities

### Core

| File | Purpose |
|------|---------|
| `main.py` | Application entry point. Initializes hardware, detects sensors, starts async tasks for sensor reading (50ms), display updates (200ms), TCP server, and mDNS. |
| `config.py` | Central configuration: GPIO pins, I2C addresses, multiplexer settings, network settings, instrument identity. |

### Sensors (`sensors/`)

| File | Purpose |
|------|---------|
| `ads1115.py` | Low-level driver for ADS1115 16-bit ADC. Reads power sensor voltage. |
| `tca9548a.py` | TCA9548A I2C multiplexer driver. Selects which sensor's EEPROM is active. |
| `eeprom.py` | AT24C02 EEPROM driver. Reads/writes sensor type, serial number, and calibration data. |
| `calibration.py` | Calibration management. Detects sensors via EEPROM, manages per-frequency calibration, handles voltage-to-dBm conversion. |
| `power_sensor.py` | High-level power measurement. `PowerChannel` handles per-channel reading and averaging. `PowerMeter` manages both channels. |

### Display (`display/`)

| File | Purpose |
|------|---------|
| `ssd1306.py` | Low-level driver for SSD1306 OLED displays. |
| `power_display.py` | Power meter UI rendering. Shows power reading, sensor type, bar graph, and IP address. |

### Network (`network/`)

| File | Purpose |
|------|---------|
| `w5500.py` | W5500 Ethernet initialization. Configures SPI, handles DHCP. |
| `tcp_server.py` | Async TCP server on port 5025 (SCPI standard). |
| `mdns.py` | Multicast DNS responder. Announces `rfmeter.local`. |

### SCPI (`scpi/`)

| File | Purpose |
|------|---------|
| `parser.py` | SCPI command parser. Handles short/long form matching. |
| `commands.py` | SCPI command implementations. |

## Hardware Design

### System Block Diagram

```
                                    ┌─────────────────────────────────┐
                                    │         Main Unit (Pico)        │
┌──────────────┐                    │                                 │
│ Sensor 1     │    Ethernet        │  ┌─────────┐    ┌──────────┐   │
│ ┌─────────┐  │    Cable           │  │TCA9548A │    │ ADS1115  │   │
│ │ RF Det  ├──┼────────────────────┼──┤ I2C Mux ├────┤ ADC #1   │   │
│ │ AD8307  │  │    (Power,I2C,     │  │  0x70   │    │  0x48    │   │
│ └─────────┘  │     Analog)        │  └────┬────┘    └──────────┘   │
│ ┌─────────┐  │                    │       │                        │
│ │ EEPROM  ├──┼────────────────────┼───────┘         ┌──────────┐   │
│ │ AT24C02 │  │                    │  ┌─────────┐    │ ADS1115  │   │
│ │  0x50   │  │                    │  │TCA9548A ├────┤ ADC #2   │   │
│ └─────────┘  │                    │  │ (ch 1)  │    │  0x49    │   │
└──────────────┘                    │  └─────────┘    └──────────┘   │
                                    │                                 │
┌──────────────┐                    │  ┌─────────┐    ┌──────────┐   │
│ Sensor 2     │    Ethernet        │  │TCA9548A │    │  OLED    │   │
│ ┌─────────┐  │    Cable           │  │ (ch 0)  │    │  0x3C    │   │
│ │ RF Det  ├──┼────────────────────┼──┴─────────┘    └──────────┘   │
│ │ AD8317  │  │                    │                                 │
│ └─────────┘  │                    │                 ┌──────────┐   │
│ ┌─────────┐  │                    │                 │  OLED    │   │
│ │ EEPROM  ├──┼────────────────────┼─────────────────┤  0x3D    │   │
│ │ AT24C02 │  │                    │                 └──────────┘   │
│ │  0x50   │  │                    │                                 │
│ └─────────┘  │                    │                 ┌──────────┐   │
└──────────────┘                    │                 │  W5500   │   │
                                    │                 │ Ethernet │   │
                                    │                 └──────────┘   │
                                    └─────────────────────────────────┘
```

### Ethernet Cable Pinout (T-568B)

Sensors connect to the main unit via standard Ethernet cables. This provides a convenient, shielded connection with enough conductors for power, I2C, and analog signals.

| Pin | Wire Color | Function | Notes |
|-----|------------|----------|-------|
| 1 | Orange/White | 3.3V | For EEPROM and 3.3V sensors |
| 2 | Orange | GND | Power ground |
| 3 | Green/White | I2C SDA | To TCA9548A mux |
| 4 | Blue | Analog Output | To ADS1115 input |
| 5 | Blue/White | Analog GND | ADC reference ground |
| 6 | Green | I2C SCL | To TCA9548A mux |
| 7 | Brown/White | 5V | For 5V sensors (AD8317, AD8318) |
| 8 | Brown | GND | Additional ground for 5V return |

**Power Supply Notes:**
- The EEPROM (AT24C02) always runs on 3.3V
- 3.3V sensors (AD8307, LTC5582): Connect RF detector VCC to pin 1
- 5V sensors (AD8317, AD8318): Connect RF detector VCC to pin 7
- Main unit must provide both 3.3V and 5V rails

### Main Unit I2C Bus

All I2C devices share a single bus:

| Device | Address | Function |
|--------|---------|----------|
| TCA9548A | 0x70 | I2C multiplexer for sensor EEPROMs |
| ADS1115 #1 | 0x48 | ADC for channel 1 (ADDR→GND) |
| ADS1115 #2 | 0x49 | ADC for channel 2 (ADDR→VDD) |
| OLED #1 | 0x3C | Display for channel 1 |
| OLED #2 | 0x3D | Display for channel 2 |

**Multiplexer Channel Mapping:**
- TCA9548A Channel 0 → Sensor 1 EEPROM
- TCA9548A Channel 1 → Sensor 2 EEPROM

All sensor EEPROMs use address 0x50. The multiplexer isolates them so only one is active at a time.

**Why Two ADS1115 ADCs?**

Each ADS1115 supports 4 single-ended or 2 differential inputs, so a single chip could theoretically handle both channels. However, this design uses one ADC per channel for the following reasons:

1. **Simultaneous sampling**: Both channels can be read at the exact same time with no phase skew or multiplexing delays. This matters when comparing signals between ports or measuring relative power.

2. **Differential measurement**: Each channel uses differential inputs (AIN0-AIN1) with a dedicated analog ground reference per sensor. This provides better noise rejection than single-ended measurements over the Ethernet cable.

3. **Simplicity**: No ADC channel switching logic is needed. Each `PowerChannel` object owns its ADC, making the software straightforward.

4. **Minimal cost impact**: ADS1115 chips are inexpensive (~$1-2), so the added hardware cost is negligible compared to the software complexity savings.

A single-ADC design would require sequential readings with mux switching, introducing timing artifacts when comparing channels.

### Pico Pin Assignments

| Function | Pico Pin | Notes |
|----------|----------|-------|
| I2C SDA | GP0 | I2C0 |
| I2C SCL | GP1 | I2C0 |
| W5500 SPI MISO | GP16 | SPI0 |
| W5500 CS | GP17 | |
| W5500 SPI SCK | GP18 | SPI0 |
| W5500 SPI MOSI | GP19 | SPI0 |
| W5500 RST | GP20 | |

### Sensor Module Schematic

Each sensor module contains an RF detector chip and an EEPROM. The EEPROM always uses 3.3V, while the RF detector can use either 3.3V or 5V depending on the chip.

**3.3V Sensor (AD8307, LTC5582):**
```
                    ┌─────────────────────────────────────────┐
                    │         Sensor Module (3.3V)            │
   RJ45             │                                         │
  ┌─────┐           │  ┌─────────────┐      ┌─────────────┐  │
  │1 3V3├───────────┼──┤ VCC         ├──────┤ VCC         │  │
  │2 GND├───────────┼──┤         GND ├──────┤         GND │  │
  │3 SDA├───────────┼──┤ SDA  EEPROM │      │ RF Detector │  │
  │4 OUT│◄──────────┼──┤     AT24C02 │      │   AD8307    ├──┼── RF IN
  │5 AGND├──────────┼──┤ SCL   0x50  │      │             │  │   (SMA)
  │6 SCL├───────────┼──┤             │      │         OUT ├──┼─► Pin 4
  │7 5V │           │  └─────────────┘      └─────────────┘  │
  │8 GND│           │                                         │
  └─────┘           └─────────────────────────────────────────┘
```

**5V Sensor (AD8317, AD8318):**
```
                    ┌─────────────────────────────────────────┐
                    │          Sensor Module (5V)             │
   RJ45             │                                         │
  ┌─────┐           │  ┌─────────────┐      ┌─────────────┐  │
  │1 3V3├───────────┼──┤ VCC         │      │         VCC ├──┼─── Pin 7 (5V)
  │2 GND├───────────┼──┤         GND ├──────┤         GND │  │
  │3 SDA├───────────┼──┤ SDA  EEPROM │      │ RF Detector │  │
  │4 OUT│◄──────────┼──┤     AT24C02 │      │   AD8318    ├──┼── RF IN
  │5 AGND├──────────┼──┤ SCL   0x50  │      │             │  │   (SMA)
  │6 SCL├───────────┼──┤             │      │         OUT ├──┼─► Pin 4
  │7 5V ├───────────┼──┼─────────────┼──────┤             │  │
  │8 GND├───────────┼──┼─────────────┼──────┴─────────────┘  │
  └─────┘           │  └─────────────┘                        │
                    └─────────────────────────────────────────┘
```

**Component List (per sensor module):**
- RF detector IC (AD8307, AD8317, AD8318, LTC5582, etc.)
- AT24C02 EEPROM (256 bytes, I2C address 0x50)
- RJ45 jack
- SMA connector for RF input
- Decoupling capacitors (100nF on each power rail)
- RF detector support components (per datasheet)

**Sensor Supply Voltage Reference:**

| Sensor | Supply | Connect VCC to |
|--------|--------|----------------|
| AD8307 | 2.7V - 5.5V | Pin 1 (3.3V) or Pin 7 (5V) |
| AD8317 | 3.0V - 5.5V | Pin 7 (5V) recommended |
| AD8318 | 4.5V - 5.5V | Pin 7 (5V) required |
| LTC5582 | 3.0V - 3.6V | Pin 1 (3.3V) only |

### Main Unit Schematic

The main unit requires both 3.3V (from Pico) and 5V (external) power supplies.

```
  5V DC ────┬──────────────────────────────────────────────────► To RJ45 Pin 7
            │
            │    Raspberry Pi Pico
            │   ┌─────────────────┐
            │   │                 │
     ┌──────┼───┤ GP0 (I2C0 SDA)  │
     │    ┌─┼───┤ GP1 (I2C0 SCL)  │
     │    │ │   │                 │
     │    │ │   │ GP16 (SPI MISO) ├────────┐
     │    │ │   │ GP17 (SPI CS)   ├───────┐│
     │    │ │   │ GP18 (SPI SCK)  ├──────┐││
     │    │ │   │ GP19 (SPI MOSI) ├─────┐│││
     │    │ │   │ GP20 (RST)      ├────┐││││
     │    │ │   │                 │    │││││
     │    │ │   │ VSYS ◄──────────┼────┼┼┼┼┼──── 5V DC (powers Pico)
     │    │ │   │ 3V3  ───────────┼─┐  │││││
     │    │ │   │ GND             ├─┼──┼┼┼┼┼─── GND
     │    │ │   └─────────────────┘ │  │││││
     │    │ │                       │  │││││
     │    │ │                       │  │││││    ┌────────────────┐
     │    │ │   ┌───────────────────┼──┼┼┼┼┘    │     W5500      │
     │    │ │   │  ┌────────────────┼──┼┼┼┘     │                │
     │    │ │   │  │  ┌─────────────┼──┼┼┘      │ RST ◄──────────┤
     │    │ │   │  │  │  ┌──────────┼──┼┘       │ CS  ◄──────────┤
     │    │ │   │  │  │  │  ┌───────┼──┘        │ SCK ◄──────────┤
     │    │ │   │  │  │  │  │       │           │ MOSI◄──────────┤
     │    │ │   │  │  │  │  │       │           │ MISO───────────┤
     │    │ │   │  │  │  │  │       └───────────┤ 3V3        GND │
     │    │ │   │  │  │  │  │                   │            ════╪══► Ethernet
     │    │ │   │  │  │  │  │                   └────────────────┘
     │    │ │   │  │  │  │  │
     │    │ │   │  │  │  │  └───────────────────────────────────────┐
     │    │ │   │  │  │  └──────────────────────────────────────┐   │
     │    │ │   │  │  └─────────────────────────────────────┐   │   │
     │    │ │   │  └────────────────────────────────────┐   │   │   │
     │    │ │   └───────────────────────────────────┐   │   │   │   │
     │    │ │                                       │   │   │   │   │
     │    │ │   ┌────────────────────┐              │   │   │   │   │
     │    │ │   │  TCA9548A (0x70)   │              │   │   │   │   │
     │    │ ├───┤ SDA            SD0 ├──► Sensor 1  │   │   │   │   │
     ├────┼─┼───┤ SCL            SC0 ├──► EEPROM    │   │   │   │   │
     │    │ │   │                SD1 ├──► Sensor 2  │   │   │   │   │
     │    │ │   │                SC1 ├──► EEPROM    │   │   │   │   │
     │    │ │   │ 3V3            GND │              │   │   │   │   │
     │    │ │   └────────────────────┘              │   │   │   │   │
     │    │ │                                       │   │   │   │   │
     │    │ │   ┌─────────────────┐   ┌─────────────────┐   │   │   │
     ├────┼─┼───┤ ADS1115 (0x48)  │   │ ADS1115 (0x49)  │   │   │   │
     │    ├─┼───┤                 │   │                 │   │   │   │
     │    │ │   │ A0 ◄── Sens1 OUT│   │ A0 ◄── Sens2 OUT│   │   │   │
     │    │ │   │ A1 ◄── AGND     │   │ A1 ◄── AGND     │   │   │   │
     │    │ │   └─────────────────┘   └─────────────────┘   │   │   │
     │    │ │                                               │   │   │
     │    │ │   ┌─────────────────┐   ┌─────────────────┐   │   │   │
     ├────┼─┼───┤ OLED (0x3C)     │   │ OLED (0x3D)     │   │   │   │
     │    └─┼───┤ Channel 1       │   │ Channel 2       │   │   │   │
     │      │   └─────────────────┘   └─────────────────┘   │   │   │
     │      │                                               │   │   │
     │      └── I2C SCL ────────────────────────────────────┘   │   │
     └──────── I2C SDA ─────────────────────────────────────────┘   │
                                                                    │
            ┌───────────────────────────────────────────────────────┘
            │
            │   RJ45 Jacks (x2)
            │   ┌─────────────────────────────────────┐
            │   │  Sensor 1          Sensor 2         │
            │   │  ┌───────┐         ┌───────┐        │
            └───┼─►│1: 3V3 │         │1: 3V3 │◄───────┼─── 3V3
   GND ─────────┼─►│2: GND │         │2: GND │◄───────┼─── GND
   I2C SDA ─────┼─►│3: SDA │         │3: SDA │◄───────┼─── (via TCA9548A)
   Sens1 OUT ───┼──│4: OUT │         │4: OUT │────────┼─── Sens2 OUT
   AGND ────────┼─►│5: AGND│         │5: AGND│◄───────┼─── AGND
   I2C SCL ─────┼─►│6: SCL │         │6: SCL │◄───────┼─── (via TCA9548A)
   5V ──────────┼─►│7: 5V  │         │7: 5V  │◄───────┼─── 5V
   GND ─────────┼─►│8: GND │         │8: GND │◄───────┼─── GND
                │  └───────┘         └───────┘        │
                └─────────────────────────────────────┘
```

**Power Supply Requirements:**
- 5V DC input (powers Pico via VSYS, and 5V sensors)
- 3.3V generated by Pico's internal regulator
- Typical current: ~200mA (depends on sensors and Ethernet activity)

## SCPI Command Reference

Connect via TCP port 5025. Commands are terminated with newline (`\n`).

### IEEE 488.2 Common Commands

| Command | Description |
|---------|-------------|
| `*IDN?` | Query instrument identification |
| `*RST` | Reset to default state |
| `*OPC?` | Query operation complete |
| `*CLS` | Clear error queue |

### Measurement Commands

| Command | Description |
|---------|-------------|
| `MEASure:POWer[1\|2]?` | Read power on channel |
| `MEASure:POWer[1\|2]:UNIT <unit>` | Set unit: `DBM`, `DBW`, `MW`, `W` |
| `MEASure:POWer[1\|2]:UNIT?` | Query current unit |
| `MEASure:POWer[1\|2]:AVERage <n>` | Set averaging (1-256) |
| `MEASure:POWer[1\|2]:AVERage?` | Query averaging |
| `MEASure:VOLTage[1\|2]?` | Read raw voltage |

### Frequency Commands

| Command | Description |
|---------|-------------|
| `SENSe:FREQuency[1\|2] <MHz>` | Set operating frequency |
| `SENSe:FREQuency[1\|2]?` | Query current frequency |
| `SENSe:FREQuency[1\|2]:CATalog?` | Query available frequencies |

### External Attenuator Commands

Use these commands when an external attenuator is placed before the sensor. The meter adds the attenuator value to all power readings, so the display and queries report the power level at the attenuator input.

| Command | Description |
|---------|-------------|
| `SENSe:ATTenuation[1\|2] <dB>` | Set external attenuator value |
| `SENSe:ATTenuation[1\|2]?` | Query attenuator value |

**Example:** With a 40 dB attenuator in front of the sensor:
```
SENS:ATT1 40           (set 40 dB attenuator on channel 1)
MEAS:POW1?             → returns +30 (sensor sees -10 dBm, adds 40 dB)
SENS:ATT1?             → 40.0
SENS:ATT1 0            (clear attenuator setting)
```

The display shows "+40dB" indicator when an attenuator is active. The `*RST` command clears attenuator settings to 0.

### Calibration Commands

Calibration is stored **per frequency** on the **sensor EEPROM**.

| Command | Description |
|---------|-------------|
| `CALibrate:POWer[1\|2]:OFFSet <dB>` | Set offset (at current frequency) |
| `CALibrate:POWer[1\|2]:OFFSet?` | Query offset |
| `CALibrate:POWer[1\|2]:SLOPe <factor>` | Set slope correction |
| `CALibrate:POWer[1\|2]:SLOPe?` | Query slope |
| `CALibrate:POWer[1\|2]:SAVE` | Save to sensor EEPROM |
| `CALibrate:POWer[1\|2]:RESTore` | Restore defaults |
| `CALibrate:SENSor[1\|2]:TYPE?` | Query sensor type |

### System Commands

| Command | Description |
|---------|-------------|
| `SYSTem:ERRor?` | Get error from queue |
| `SYSTem:VERSion?` | Query SCPI version |
| `SYSTem:NET:IP?` | Query IP address |
| `SYSTem:NET:MAC?` | Query MAC address |

## Calibration

### How It Works

1. **Sensor identification**: At startup, the main unit reads each sensor's EEPROM to get sensor type, serial number, and calibration frequencies.

2. **Calibration storage**: Each sensor stores its own calibration data. When you move a sensor to a different channel or different meter, the calibration follows.

3. **Per-frequency corrections**: RF detectors have frequency-dependent response. Store separate offset/slope for each calibration frequency.

### EEPROM Data Format

The sensor EEPROM (256 bytes) stores:

| Offset | Size | Content |
|--------|------|---------|
| 0-3 | 4 | Magic: "RFPM" |
| 4 | 1 | Format version |
| 5 | 1 | Sensor type length |
| 6-13 | 8 | Sensor type string |
| 14 | 1 | Serial number length |
| 15-26 | 12 | Serial number string |
| 27-30 | 4 | Base slope (float) |
| 31-34 | 4 | Base intercept (float) |
| 35 | 1 | Number of frequencies |
| 36-67 | 32 | Frequencies (up to 16 × 2 bytes) |
| 68 | 1 | Number of cal entries |
| 69+ | 10 each | Per-frequency cal (freq + offset + slope) |

### Calibration Procedure

1. **Set frequency:**
   ```
   SENS:FREQ1 100
   ```

2. **Apply reference signal** (e.g., -20 dBm at 100 MHz)

3. **Read and correct:**
   ```
   MEAS:POW1?        → -22.5
   CAL:POW1:OFFS 2.5
   ```

4. **Repeat for other frequencies**

5. **Save to sensor EEPROM:**
   ```
   CAL:POW1:SAVE
   ```

### Programming New Sensors

Use the `SensorEEPROM.format_new_sensor()` method to initialize a new sensor module:

```python
from machine import I2C, Pin
from sensors.eeprom import SensorEEPROM

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
eeprom = SensorEEPROM(i2c, 0x50)

eeprom.format_new_sensor(
    sensor_type="AD8307",
    serial="SN001",
    slope=0.025,           # 25 mV/dB
    intercept=-84.0,       # dBm at 0V
    frequencies=[50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
)
```

## Network Discovery

The instrument announces itself via mDNS:
- Hostname: `rfmeter.local`
- Service: `_scpi-raw._tcp` on port 5025

**Discover:**
```bash
dns-sd -B _scpi-raw._tcp
```

**Connect:**
```bash
nc rfmeter.local 5025
```

## Deployment

1. Copy all files to the Pico maintaining directory structure
2. Program each sensor module's EEPROM with sensor info
3. Connect sensors via Ethernet cables to RJ45 jacks
4. Connect Ethernet to network
5. Power on - sensors auto-detected, DHCP acquired
6. Access via `rfmeter.local:5025`
