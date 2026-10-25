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
│ Head ADC,   │ │ 256x64 OLED │ │ Ethernet &  │ │  Command    │
│ temp, EEPROM│ │ both chans  │ │ TCP server  │ │  parsing    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

## Key Features

- **EEPROM-based calibration**: Each sensor module stores its own calibration data in an onboard EEPROM. Calibration travels with the sensor, not the channel.
- **Frequency-dependent calibration**: Store separate offset/slope corrections for each calibration frequency.
- **Self-contained sensor heads**: Each head carries its detector, 16-bit ADC, temperature sensor and EEPROM. Only power and I2C travel over the cable.
- **One I2C bus per head**: Each sensor head hangs on its own Pico I2C controller (I2C0 for channel 1, I2C1 for channel 2), so heads are interchangeable and no multiplexer is needed.
- **Hot-swappable sensors**: Sensors are automatically detected at startup and on plug-in via a presence detect line.
- **Single 256x64 grayscale OLED**: An SSD1322 panel over SPI shows both channels side by side.
- **SCPI control**: Standard SCPI commands over TCP port 5025.
- **mDNS discovery**: Find the meter as `rfmeter.local`.

## File Responsibilities

### Core

| File | Purpose |
|------|---------|
| `main.py` | Application entry point. Initializes hardware, detects sensors, starts async tasks for sensor reading (50ms), display updates (200ms), TCP server, and mDNS. |
| `config.py` | Central configuration: GPIO pins, I2C buses and addresses, display SPI, network settings, instrument identity. |

### Sensors (`sensors/`)

| File | Purpose |
|------|---------|
| `ads1115.py` | Low-level driver for the ADS1115 16-bit ADC in each sensor head. Continuous-conversion mode; reads never block. |
| `mcp9808.py` | Driver for the MCP9808 temperature sensor in each sensor head. |
| `eeprom.py` | AT24Cxx EEPROM driver. Reads/writes sensor type, serial number, and calibration data. |
| `calibration.py` | Calibration management. Holds the per-channel I2C buses, detects sensors via EEPROM, manages per-frequency calibration, handles voltage-to-dBm conversion. |
| `power_sensor.py` | High-level power measurement. `PowerChannel` handles per-channel reading and averaging. `PowerMeter` manages both channels. |

### Display (`display/`)

| File | Purpose |
|------|---------|
| `ssd1322.py` | Low-level driver for the SSD1322 256x64 4-bit grayscale OLED (4-wire SPI). Frame buffer is `framebuf.GS4_HMSB`, which matches the controller's RAM layout. |
| `power_display.py` | Power meter UI rendering. Splits the panel into two panes, one per channel: large reading, unit, bar graph, sensor type, head temperature; IP address and hostname on a shared status line. |

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

### Design Principle: Digital-Only Cable

Each sensor head contains the complete analog signal chain: RF detector,
RC filter and a 16-bit ADS1115 ADC. The head also carries an EEPROM
(identity and calibration) and an MCP9808 temperature sensor next to the
detector, plus its own voltage regulators. The cable to the main unit
carries only an 8V supply rail, I2C and a presence line.

This keeps the detector's millivolt-level output off the cable, so cable
length, connector contact resistance and ground offsets between units no
longer affect the reading.

### System Block Diagram

```
┌──────────────────────────────────┐              ┌──────────────────────────────┐
│ Sensor Head 1                    │              │       Main Unit (Pico)       │
│                                  │              │                              │
│  RF IN   ┌─────────┐  ┌────────┐ │   Ethernet   │     ┌──────────────────┐     │
│  (SMA) ──┤ AD8307  ├─►│ADS1115 ├─┤   cable      │     │       Pico       │     │
│          └─────────┘  │  0x48  │ │ (8V + I2C)   │     │                  │     │
│          ┌─────────┐  └────────┤ │              │     │ I2C0 (GP0/GP1)   │     │
│          │ MCP9808 ├───────────┼─┼══════════════┼─────┤                  │     │
│          │  0x18   │  ┌────────┤ │              │     │ I2C1 (GP2/GP3)   │     │
│          └─────────┘  │ EEPROM │ │              │  ┌──┤                  │     │
│                       │  0x50  │ │              │  │  │ SPI0 (GP16-19)   ├──┐  │
│                       └────────┘ │              │  │  │ SPI1 (GP10/11)   ├┐ │  │
└──────────────────────────────────┘              │  │  └──────────────────┘│ │  │
                                                  │  │                      │ │  │
┌──────────────────────────────────┐              │  │  ┌───────────────┐   │ │  │
│ Sensor Head 2                    │              │  │  │  SSD1322 OLED │◄──┘ │  │
│                                  │              │  │  │  256 x 64     │     │  │
│  RF IN   ┌─────────┐  ┌────────┐ │   Ethernet   │  │  └───────────────┘     │  │
│  (SMA) ──┤ AD8318  ├─►│ADS1115 ├─┤   cable      │  │  ┌───────────────┐     │  │
│          └─────────┘  │  0x48  │ │ (8V + I2C)   │  │  │     W5500     │◄────┘  │
│          ┌─────────┐  └────────┤ │              │  │  │   Ethernet    │        │
│          │ MCP9808 ├───────────┼─┼══════════════┼──┘  └───────────────┘        │
│          │  0x18   │  ┌────────┤ │              │                              │
│          └─────────┘  │ EEPROM │ │              │                              │
│                       │  0x50  │ │              │                              │
│                       └────────┘ │              │                              │
└──────────────────────────────────┘              └──────────────────────────────┘
```

Every head uses the same I2C addresses, so the heads are interchangeable.
The RP2040 has two independent I2C controllers; each one is wired to one
RJ45 jack, so head 1 is always on I2C0 and head 2 on I2C1. Nothing else
shares those buses.

### Ethernet Cable Pinout (T-568B)

Sensors connect to the main unit via standard Ethernet cables. Only power
and digital signals are carried.

Each I2C line shares a twisted pair with its own ground return, which
keeps SDA-to-SCL crosstalk low and gives each signal a tight return path.

| Pin | Pair | Wire Color | Function | Notes |
|-----|------|------------|----------|-------|
| 1 | Orange | Orange/White | V+ (8V) | Head supply from the main unit's LM317, fused per port |
| 2 | Orange | Orange | GND | Power return |
| 3 | Green | Green/White | I2C SDA | Pico I2C0 (head 1) or I2C1 (head 2) |
| 6 | Green | Green | GND | Return for SDA |
| 4 | Blue | Blue | I2C SCL | Pico I2C0 (head 1) or I2C1 (head 2) |
| 5 | Blue | Blue/White | GND | Return for SCL |
| 7 | Brown | Brown/White | GND | Return for presence detect |
| 8 | Brown | Brown | Presence Detect | Tied to GND in the head; pulled up in the main unit |

**Power Supply Notes:**
- The cable carries a single V+ of 8V, made by an LM317 on the main
  board. Each head still regulates its own 3.3V (and 5V where the
  detector needs it), so cable drop, contact resistance and main-unit
  supply noise do not reach the analog parts.
- The EEPROM, ADS1115 and MCP9808 always run on the head's 3.3V
- 3.3V detectors (AD8307, LTC5582): detector VCC from the head's 3.3V LDO
- 5V detectors (AD8317, AD8318): detector VCC from the head's 5V LDO
- Pins 2, 5, 6 and 7 are all GND and tied together at both ends; no
  conductor in the cable floats

**Hot-Swap Detection:**
- Pin 8 is tied to GND in each sensor head
- Main unit pulls each presence detect GPIO up to 3.3V (10kΩ, plus the
  RP2040 internal pull-up)
- When sensor is connected: GPIO reads LOW
- When sensor is disconnected: GPIO reads HIGH
- Either edge triggers sensor re-detection, which also re-configures the
  head's ADC (it powers up in single-shot mode)
- A ground tie needs no working rail in the head, so a head with a dead
  regulator still registers as present and can be reported as faulty

### I2C Topology

The main unit has no I2C devices of its own. Each of the Pico's two
I2C controllers runs straight to one RJ45 jack:

| Pico bus | Pins | Goes to |
|----------|------|---------|
| I2C0 | GP0 (SDA), GP1 (SCL) | RJ45 #1, sensor head 1 |
| I2C1 | GP2 (SDA), GP3 (SCL) | RJ45 #2, sensor head 2 |

**Sensor head bus (identical in every head):**

| Device | Address | Function |
|--------|---------|----------|
| ADS1115 | 0x48 | ADC for detector output (ADDR → GND) |
| MCP9808 | 0x18 | Temperature next to the detector (A0-A2 → GND) |
| AT24C02 / AT24CS04 | 0x50 | Sensor type, serial number, calibration |

Because the heads never share a bus, there is no multiplexer and no
channel-select transaction. A fault on one cable (a head yanked
mid-transfer, a shorted SDA) can only hang that channel's bus; the other
channel and the display are unaffected.

**Why One ADS1115 Per Head?**

1. **No analog on the cable**: The detector output is digitised within a
   few centimetres of the detector.
2. **Interchangeable heads**: Every head looks the same to the main unit.
   Calibration, identity and ADC travel together.
3. **Independent sampling**: Both ADCs free-run in continuous mode at
   128 SPS on separate buses. The Pico just reads the latest conversion
   from each head, so reads do not block and the two channels are
   sampled within a millisecond of each other.
4. **Spare inputs**: AIN2/AIN3 are free for future heads with two
   detectors (e.g. a directional coupler head reporting forward and
   reflected power).

**Why a Temperature Sensor in the Head?**

Logarithmic detectors drift with temperature (AD8307: roughly ±0.3 dB
over -40 to +85 °C, AD8318 somewhat more). Measuring the temperature
at the detector allows this drift to be characterised per head and
compensated in firmware. The reading is available via
`MEASure:TEMPerature[1|2]?`. Temperature compensation coefficients are
not yet stored in the EEPROM format (see format version in `eeprom.py`).

### Pico Pin Assignments

| Function | Pico Pin | Notes |
|----------|----------|-------|
| Head 1 I2C SDA | GP0 | I2C0 → RJ45 #1 pin 3 |
| Head 1 I2C SCL | GP1 | I2C0 → RJ45 #1 pin 4 |
| Head 2 I2C SDA | GP2 | I2C1 → RJ45 #2 pin 3 |
| Head 2 I2C SCL | GP3 | I2C1 → RJ45 #2 pin 4 |
| Sensor 1 Detect | GP4 | Pull-up, active low, IRQ on edge |
| Sensor 2 Detect | GP5 | Pull-up, active low, IRQ on edge |
| Display SPI SCK | GP10 | SPI1 |
| Display SPI MOSI | GP11 | SPI1 TX (SSD1322 is write-only) |
| Display CS | GP13 | Active low |
| Display D/C | GP14 | High = data, low = command |
| Display RST | GP15 | Active low |
| W5500 SPI MISO | GP16 | SPI0 |
| W5500 CS | GP17 | |
| W5500 SPI SCK | GP18 | SPI0 |
| W5500 SPI MOSI | GP19 | SPI0 |
| W5500 RST | GP20 | |
| W5500 INT | GP21 | Not used by the firmware |

The controller is a W5500-EVB-Pico, so the W5500 and its SPI wiring
(GP16-GP21) are on the module itself. GP6-GP9, GP12, GP22 and GP26-GP28
are free (front panel buttons, encoder, status LED).

### Sensor Head Schematic

Each sensor head contains an RF detector, an ADS1115 ADC, an MCP9808
temperature sensor, an EEPROM and its own voltage regulation. The cable
delivers 8V; the head makes a 3.3V rail for the digital parts and, for
5V detectors, a 5V rail as well.

```
                 ┌──────────────────────────────────────────────────────────────────┐
                 │                          Sensor Head                             │
   RJ45          │                                                                  │
  ┌─────┐        │  ┌─────┐  ┌───────────┐   5V (detector)   ┌───────────┐          │
  │1 V+ ├────────┼──┤ TVS ├──┤ 5V LDO    ├────────┬──────────┤ 3.3V LDO  ├──┬─ 3V3  │
  │2 GND├────────┼┐ │10µF │  │ 5V heads  │        │          │           │  │       │
  │3 SDA├──────┐ ││ └─────┘  └───────────┘        │          └───────────┘  │       │
  │6 GND├──────┼─┤│     (3.3V heads: V+ feeds the 3.3V LDO directly)        │       │
  │4 SCL├────┐ │ ││                               │                         │       │
  │5 GND├────┼─┼─┤│                               │                         │       │
  │7 GND├────┼─┼─┤│   ┌──────────┐  ┌──────────┐  │  ┌──────────┐           │       │
  │8 DET├─┐  │ │ ││   │ ADS1115  │  │ MCP9808  │  │  │ EEPROM   │           │       │
  └─────┘ │  │ │ ││   │  0x48    ├──┤  0x18    ├──┼──┤  0x50    ├───────────┘       │
         GND │ │ ││   │ SDA  SCL │  │ SDA  SCL │  │  │ SDA  SCL │  (all on 3V3)     │
             │ │ ││   └──┬────┬──┘  └──┬────┬──┘  │  └──┬────┬──┘                   │
             └─┼─┼┼──────┴────┼────────┴────┼─────┼─────┴────┼──── SDA  [4.7k → 3V3] │
               └─┼┼───────────┴─────────────┴─────┼──────────┴──── SCL  [4.7k → 3V3] │
                 ││                               │                                  │
                 ││   ADS1115 AIN0 ◄──────────┬── OUT  ┌─────────────┐              │
                 ││                        [100nF]     │ RF Detector │              │
                 ││   ADS1115 AIN1 ◄──────────┴── COM  │   AD8307    ├─[3dB pad]─ SMA│
                 ││                                    │ VCC ◄───────┼── 3V3 or 5V   │
                 │└─ GND                               └─────────────┘   rail        │
                 │                                                                  │
                 │   ADS1115: ADDR → GND, ALERT/RDY → 10kΩ pull-up, AIN2/AIN3 spare  │
                 └──────────────────────────────────────────────────────────────────┘
```

**Component List (per sensor head):**
- RF detector IC (AD8307, AD8317, AD8318, LTC5582, etc.)
- ADS1115 16-bit ADC (TSSOP-10), ADDR → GND
- MCP9808 temperature sensor (MSOP-8 or DFN-8), A0-A2 → GND, placed as close to the detector as layout allows
- AT24C02 / AT24CS04 EEPROM (I2C address 0x50; A1/A2 → GND)
- 3.3V low-noise LDO (e.g. LP2985-33 or MIC5205-3.3, SOT-23-5, 16V input) for ADC, temperature sensor, EEPROM and 3.3V detectors
- 5V LDO (e.g. AP7361C-50 or LD1117S50, SOT-223) on 5V-detector heads only; the 3.3V LDO then cascades from the 5V rail
- Power input: 10µF ceramic + 12V TVS (SMF12A or similar) on V+, 1µF + 100nF on each LDO output
- RJ45 jack: Würth 615108150221R mid-mount (shielded, tab down, no magnetics, no LEDs; project library `rf_power_meter:RJ45_WE-615108150221R`), sits in a board-edge cutout to fit the enclosure height; pin 8 tied to GND for presence detect
- SMA connector for RF input: Amphenol RF 132289, edge mount (project library `rf_power_meter:SMA_132289`)
- 3 dB pi attenuator between SMA and detector: 17.4Ω series, 2× 294Ω shunt, thin-film 1% (see `hardware/README.md`)
- Detector output filter: 100nF from OUT to ground, straight into ADS1115 AIN0 (the AD8307 output is 12.5kΩ, no series resistor needed)
- Detector input network: 52.3Ω termination, 2× 1nF C0G coupling capacitors on INP and INM (see `hardware/README.md`)
- Decoupling capacitors (100nF on each IC supply pin)
- I2C pull-up resistors (2× 4.7kΩ to the head's 3V3)
- 10kΩ pull-up on ADS1115 ALERT/RDY (unused, keeps the open-drain output defined)
- ESD protection (1× ESDAVLC6-2BLY for I2C lines)
- RF detector support components (per datasheet)

**Detector Supply Voltage Reference:**

| Sensor | Supply | Head rail for detector | Max output | Fits ADS1115 at 3.3V? |
|--------|--------|------------------------|------------|------------------------|
| AD8307 | 2.7V - 5.5V | 3.3V (5V optional) | ~2.5V | Yes |
| AD8317 | 3.0V - 5.5V | 5V recommended | ~2.1V | Yes |
| AD8318 | 4.5V - 5.5V | 5V required | ~2.1V | Yes |
| LTC5582 | 3.0V - 3.6V | 3.3V only | ~2.1V | Yes |

The ADS1115 runs from 3.3V in all heads. Its inputs must stay below
VDD + 0.3V, which every listed detector satisfies even when powered from 5V.
The PGA is set to ±4.096V (125 µV/LSB); for a detector with a 25 mV/dB
slope that is 0.005 dB per count.

### Main Unit Schematic

The main unit takes 12V DC from a 1A adapter. Three regulators make the
rails: an LM317M set to 8V for the two RJ45 ports (fused per port), a 5V
buck module for the W5500-EVB-Pico, whose own 3.3V regulator powers the
RP2040 and the W5500, and a small 3.3V LDO for the OLED module. With the
analog chain moved to the heads, the main unit is purely digital.

```
  12V DC ───┬──► LM317M (8V) ─────────────────────────────────► To RJ45 Pin 1 (V+)
            │                                                     via polyfuse + TVS per port
            ├──► 5V buck module ───────┬──► Pico VSYS (RP2040 + W5500)
            │                          └──► 3.3V LDO ──► OLED module
            │
            │    Raspberry Pi Pico
            │   ┌─────────────────┐
            │   │ GP0 (I2C0 SDA)  ├──[10kΩ to 3V3]──► RJ45 #1 pin 3 (SDA)
            │   │ GP1 (I2C0 SCL)  ├──[10kΩ to 3V3]──► RJ45 #1 pin 4 (SCL)
            │   │ GP2 (I2C1 SDA)  ├──[10kΩ to 3V3]──► RJ45 #2 pin 3 (SDA)
            │   │ GP3 (I2C1 SCL)  ├──[10kΩ to 3V3]──► RJ45 #2 pin 4 (SCL)
            │   │ GP4 (DET1)      ├◄─[10kΩ to 3V3]─── RJ45 #1 pin 8 (low = present)
            │   │ GP5 (DET2)      ├◄─[10kΩ to 3V3]─── RJ45 #2 pin 8 (low = present)
            │   │                 │
            │   │ GP10 (SPI1 SCK) ├────────┐
            │   │ GP11 (SPI1 TX)  ├───────┐│
            │   │ GP13 (CS)       ├──────┐││
            │   │ GP14 (D/C)      ├─────┐│││
            │   │ GP15 (RST)      ├────┐││││       ┌──────────────────────┐
            │   │                 │    │││││       │   SSD1322 OLED       │
            │   │                 │    ││││└───────┤ SCLK      256 x 64   │
            │   │                 │    │││└────────┤ SDIN                 │
            │   │                 │    ││└─────────┤ CS#                  │
            │   │                 │    │└──────────┤ D/C#                 │
            │   │                 │    └───────────┤ RES#                 │
            │   │                 │                │ VDD (3.3V)  GND      │
            │   │                 │                └──────────────────────┘
            │   │ GP16 (SPI MISO) ├────────┐
            │   │ GP17 (SPI CS)   ├───────┐│
            │   │ GP18 (SPI SCK)  ├──────┐││
            │   │ GP19 (SPI MOSI) ├─────┐│││
            │   │ GP20 (RST)      ├────┐││││       ┌────────────────┐
            │   │                 │    │││││       │     W5500      │
            │   │                 │    ││││└───────┤ MISO           │
            │   │                 │    │││└────────┤ MOSI           │
            │   │                 │    ││└─────────┤ SCK            │
            │   │                 │    │└──────────┤ CS             │
            │   │                 │    └───────────┤ RST            │
            │   │ VSYS ◄──────────┼──── 5V         │ 3V3        GND │
            │   │ GND             ├──── GND        │            ════╪══► Ethernet
            │   └─────────────────┘                └────────────────┘

                RJ45 Jacks (x2)
                ┌─────────────────────────────────────┐
                │  Sensor 1          Sensor 2         │
                │  ┌───────┐         ┌───────┐        │
   V+ (fused) ──┼─►│1: V+  │         │1: V+  │◄───────┼─── V+ (fused)
   GND ─────────┼─►│2: GND │         │2: GND │◄───────┼─── GND
   GP0 (SDA0) ──┼─►│3: SDA │         │3: SDA │◄───────┼─── GP2 (SDA1)
   GP1 (SCL0) ──┼─►│4: SCL │         │4: SCL │◄───────┼─── GP3 (SCL1)
   GND ─────────┼─►│5: GND │         │5: GND │◄───────┼─── GND
   GND ─────────┼─►│6: GND │         │6: GND │◄───────┼─── GND
   GND ─────────┼─►│7: GND │         │7: GND │◄───────┼─── GND
   GP4 (DET1) ──┼──│8: DET │         │8: DET │────────┼─── GP5 (DET2)
                │  └───────┘         └───────┘        │
                └─────────────────────────────────────┘
```

**Display:**
- SSD1322 controller, 256x64 pixels, 4-bit grayscale (16 levels)
- 4-wire SPI at up to 10 MHz on the Pico's SPI1; the controller is
  write-only, so MISO is not connected
- 3.3V logic (VDDIO 1.65-3.5V), so no level shifting
- A full frame is 8 KB; at 10 MHz a refresh takes about 7 ms. The
  firmware redraws at 5 Hz
- Both channels share the panel: channel 1 on the left half, channel 2
  on the right, with IP address and mDNS name on a status line

**Power Supply Requirements:**
- 12V DC input from a 1A AC/DC adapter (2.1mm jack, centre positive)
- An LM317M (TO-220, 500mA) set to 8V with R1 = 240Ω, R2 = 1.3kΩ makes
  the head rail. It dissipates under 0.7W with two AD8318 heads and
  needs no heatsink
- The 8V rail goes to each RJ45 pin 1 through a resettable fuse (~200mA
  hold) and a 12V TVS, so a shorted cable or head only drops that port
- A 1A 5V buck module (R-78B5.0-1.0 or TSR 1-2450 class) feeds Pico VSYS
- On the W5500-EVB-Pico the W5500 shares the module's 3.3V regulator
  with the RP2040, so it is covered by the 5V feed to VSYS
- A separate 3.3V LDO (SOT-223, e.g. AP7361C-33 or AMS1117-3.3) from the
  5V rail supplies the OLED module. A 256x64 OLED module with its onboard
  panel-voltage boost can draw 100-200 mA at full brightness, and the
  Pico's 3V3 pin is already carrying the W5500. Skip the LDO if the
  module accepts 5V on its own regulator input
- Each head draws roughly 1 mA of digital current plus the detector's
  supply (AD8307 ~8 mA, AD8317 ~22 mA, AD8318 ~68 mA)
- Typical total input current: ~250mA at 12V (depends on detectors,
  display content and Ethernet activity); the 1A adapter has ample margin

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
| `MEASure:VOLTage[1\|2]?` | Read raw detector voltage |
| `MEASure:TEMPerature[1\|2]?` | Read sensor head temperature (°C) |

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
    intercept=-81.0,       # dBm at 0V, referred to the SMA (AD8307 -84 dBm + 3 dB pad)
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
