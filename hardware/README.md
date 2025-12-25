# Hardware Design

KiCad 9 project files for the RF Power Meter.

## Directory Structure

- `main_unit/` - Main unit PCB with Pico, W5500, ADCs, displays, and RJ45 jacks
- `sensor_module/` - Sensor module PCB template (RF detector + EEPROM)

## Design Notes

See the main [README.md](../README.md) for:
- System block diagram
- Ethernet cable pinout (T-568B)
- I2C bus addresses
- Pico pin assignments
- Sensor module schematics (3.3V and 5V variants)

## Analog Input Conditioning

The sensor analog outputs (RJ45 pins 4 and 5) connect to the ADS1115 differential inputs via simple conditioning:

```
                        TVS
                         │
RJ45 Pin 4 (OUT) ────────┼────[100Ω]───┬─── ADS1115 AIN0
                         ┴              │
                        ───          [100nF]
                         │              │
                        GND            GND

                         │
RJ45 Pin 5 (AGND)────────┼────[100Ω]───┬─── ADS1115 AIN1
                         ┴              │
                        ───          [100nF]
                         │              │
                        GND            GND
```

**TVS Diodes (ESD Protection):**
- Part: PESD5V0L2BT-Q (Nexperia, SOT-23, dual diode)
- Standoff voltage: 5V (safe for 0-3.3V sensor signals)
- Clamping voltage: ~12V @ 8kV ESD
- Capacitance: ~1pF (negligible signal impact)
- Place close to RJ45 connector to catch ESD before it reaches the PCB

**RC Low-Pass Filter:**
- R: 100Ω per line (keeps ADS1115 source impedance low for proper settling)
- C: 100nF to ground (forms ~1.6kHz low-pass, attenuates RF and HF noise)

No amplification is needed - RF detector outputs (0.2V to 2.5V typical) are well-matched to the ADS1115 at ±4.096V PGA setting, giving ~16,000 counts of resolution across the signal range.

## I2C ESD Protection

The I2C lines (SDA, SCL - RJ45 pins 3 and 6) are exposed to ESD during cable insertion and should be protected:

```
RJ45 Pin 3 (SDA) ────────┬──── TCA9548A SDA
                         ┴
                        ───  TVS (PESD5V0L2BT-Q)
                         │
                        GND

RJ45 Pin 6 (SCL) ────────┬──── TCA9548A SCL
                         ┴
                        ───
                         │
                        GND
```

One PESD5V0L2BT-Q (dual diode) protects both SDA and SCL per connector. The ~1pF capacitance per line is negligible for 400kHz I2C (bus limit is 400pF).

## Presence Detect Conditioning

The presence detect line (RJ45 pin 8) needs a pull-down resistor and ESD protection:

```
RJ45 Pin 8 (DET) ────────┬────────┬──── GP2/GP3
                         ┴        │
                        ───    [10kΩ]
                         │        │
                        GND      GND
                        TVS    Pull-down
```

- **Pull-down (10kΩ):** The RP2040's internal pull-down (~50kΩ) is weak. An external 10kΩ provides better noise immunity when the sensor is disconnected, especially with long cables in an RF environment.
- **TVS:** One PESD5V0L2BT-Q per connector (one diode unused, or share between both RJ45 presence detect lines).

## ESD Protection Summary

TVS diodes per RJ45 connector (place close to connector):

| Signals | RJ45 Pins | TVS Package | Notes |
|---------|-----------|-------------|-------|
| Analog OUT + AGND | 4, 5 | 1× PESD5V0L2BT-Q | Before RC filter |
| I2C SDA + SCL | 3, 6 | 1× PESD5V0L2BT-Q | ~1pF OK for 400kHz |
| Presence Detect | 8 | 1× PESD5V0L2BT-Q | One diode unused |

Total: 6× PESD5V0L2BT-Q for both RJ45 connectors (or 5× if presence detect lines share one package).
