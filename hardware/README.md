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
