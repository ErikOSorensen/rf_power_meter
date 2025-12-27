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

## I2C Pull-Up Resistors

I2C is open-drain and requires pull-ups. The RP2040's internal pull-ups (~50-80kΩ) are too weak for reliable operation.

**Main I2C bus (near Pico):**

```
3.3V ────┬───────┬────
         │       │
      [2.2kΩ] [2.2kΩ]
         │       │
        SDA     SCL ──── to TCA9548A, ADS1115s, OLEDs
```

**Muxed I2C channels (TCA9548A outputs to RJ45):**

The TCA9548A passes signals through but provides no pull-ups. The Ethernet cable adds capacitance (~50-100pF/m). Pull-ups are needed on both ends:

```
Main Unit:                            Sensor Module:

TCA9548A SD0/SC0 ──┬── RJ45 ══════════ RJ45 ──┬── EEPROM SDA/SCL
                   │                          │
                [10kΩ]                     [4.7kΩ]
                   │                          │
                  3.3V                       3.3V
```

- **Main unit (10kΩ):** Weaker pull-up keeps lines defined when no sensor is connected
- **Sensor module (4.7kΩ):** Stronger pull-up handles cable capacitance
- **Combined (10kΩ ∥ 4.7kΩ ≈ 3.2kΩ):** Adequate for cable length when connected

**Pull-up summary:**

| Location | Value | Quantity | Purpose |
|----------|-------|----------|---------|
| Main bus (SDA, SCL) | 2.2kΩ | 2 | Primary pull-up for on-board devices |
| Mux CH0 output (SD0, SC0) | 10kΩ | 2 | Keep lines defined, sensor 1 |
| Mux CH1 output (SD1, SC1) | 10kΩ | 2 | Keep lines defined, sensor 2 |
| Sensor module (SDA, SCL) | 4.7kΩ | 2 per module | Handle cable capacitance |

## ADS1115 ADC Configuration

**ADDR pin (I2C address selection):**

| ADC | Address | ADDR Pin |
|-----|---------|----------|
| ADS1115 #1 (Channel 1) | 0x48 | GND |
| ADS1115 #2 (Channel 2) | 0x49 | 3.3V |

The ADDR pin must be tied directly to GND or VDD - do not leave floating.

**ALERT/RDY pin:**

The ALERT/RDY pin can signal conversion complete (avoids polling) or comparator alerts. The current software polls the config register, so this pin is unused.

Add a pull-up to keep the open-drain output in a defined state:

```
3.3V
 │
[10kΩ]
 │
ADS1115 ALERT/RDY
```

Do this for both ADS1115 chips. No GPIO connection is needed for the current software.

## TCA9548A I2C Multiplexer Configuration

**Address pins (A0, A1, A2):**

All tied to GND for address 0x70:

| Pin | Connection |
|-----|------------|
| A0 | GND |
| A1 | GND |
| A2 | GND |

**RESET pin:**

Connect to GP4 with a pull-up for optional software reset capability:

```
3.3V
 │
[10kΩ]
 │
 ├──── TCA9548A RESET
 │
GP4
```

- Normal operation: GP4 as input (high-Z), RESET held high by pull-up
- Bus recovery: Pull GP4 low to reset mux, clears all channel selections

This allows recovery if the I2C bus gets stuck.

**Unused channels (2-7):**

Leave SDA2-7 and SCL2-7 unconnected. Do NOT tie to ground - if accidentally selected, this would short the I2C bus.

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

## Sensor Module ESD Protection

The sensor module's RJ45 is also exposed when disconnected, and the module is handled frequently. Add TVS protection for the EEPROM I2C lines:

```
        Sensor Module

                 3.3V
                  │
               [4.7kΩ]
                  │
RJ45 Pin 3 ──────┴──────── EEPROM SDA
  (SDA)           │
                 ───
                  ┴  TVS
                 GND

                 3.3V
                  │
               [4.7kΩ]
                  │
RJ45 Pin 6 ──────┴──────── EEPROM SCL
  (SCL)           │
                 ───
                  ┴  TVS (same package)
                 GND
```

- **Part:** 1× PESD5V0L2BT-Q per sensor module (protects both SDA and SCL)
- **Placement:** Close to RJ45 connector
- **Cost:** ~$0.10 per module

The RF detector output typically has internal ESD protection and doesn't require external TVS on the sensor module (the main unit protects this line).
