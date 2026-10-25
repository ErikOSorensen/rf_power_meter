# Hardware Design

KiCad project files for the RF Power Meter.

## Directory Structure

- `main_board/` - Main unit PCB: Pico, W5500, SSD1322 OLED header, RJ45 jacks
- `sensor_heads/AD8307/` - AD8307 sensor head (detector + ADC + temperature sensor + EEPROM). Template for other heads.
- `lib/` - Project-local KiCad library (symbols, footprints, 3D models). See `lib/README.md`.

## Design Notes

See the main [README.md](../README.md) for:
- System block diagram
- Ethernet cable pinout (T-568B)
- I2C topology and addresses
- Pico pin assignments
- Sensor head schematic and component list

The cable between main unit and head carries only power and I2C. All
analog conditioning lives in the sensor head.

## Sensor Head: Power

The cable delivers V+ = 8V on RJ45 pin 1 (from the LM317 on the main
board, see below). Every head regulates locally anyway, so the analog
parts never see the cable:

```
                 ┌──────────┐
RJ45 pin 1 ──┬───┤ 5V LDO   ├──┬──── 5V: detector (5V heads only)
   (V+)      │   │ SOT-223  │  │
          [10µF] └──────────┘  │   ┌──────────┐
             │                 └───┤ 3.3V LDO ├──┬──── 3V3: ADS1115, MCP9808,
          [TVS 12V]                │ SOT-23-5 │  │           EEPROM, pull-ups,
             │                     └──────────┘ [1µF]        3.3V detector
            GND                                  │
                                                GND
```

- **3.3V LDO:** low-noise, 16V-input, 150mA class. LP2985-33 or MIC5205-3.3
  (SOT-23-5). This rail feeds the ADC, so noise matters more than
  efficiency; a buck converter is not appropriate here.
- **5V LDO (5V-detector heads only):** AP7361C-50 or LD1117S50 in SOT-223.
  The 3.3V LDO then takes its input from the 5V rail, so the hot part is
  the SOT-223 and the 3.3V regulator sees only ~1.7V across it.
- **3.3V-detector heads:** omit the 5V LDO, feed the 3.3V LDO from V+.
- **Input protection:** 10µF ceramic (25V rated) and a 12V TVS (SMF12A or
  similar) on V+ at the RJ45. The RJ45 is keyed, so reverse polarity
  protection is optional; a Schottky in series costs 0.3V of headroom if
  wanted.
- **Outputs:** 1µF + 100nF on each LDO output, plus 100nF at every IC.

**Dissipation at 8V input:**

| Head | Regulator | Current | Drop | Power | Package |
|------|-----------|---------|------|-------|---------|
| AD8307 (3.3V) | 3.3V LDO | ~10mA | 4.7V | ~50mW | SOT-23-5, fine |
| AD8318 (5V) | 5V LDO | ~70mA | 3V | ~210mW | SOT-223 (~60°C/W), ~13°C rise |
| AD8318 (5V) | 3.3V LDO | ~2mA | 1.7V | ~3mW | SOT-23-5, fine |

Allowing for cable drop and LM317 tolerance the 5V LDO still has well
over 2V of headroom, more than the 1.1V dropout of an LD1117 at this
current. The 12V TVS on V+ stays: its 12V standoff is comfortably above
the 8V rail.

## Sensor Head: Detector to ADC

The detector output drives the ADS1115 differential input directly, with
one filter capacitor, all on the head PCB:

```
AD8307 OUT ─────────────┬─── ADS1115 AIN0
                        │
                     [100nF]
                        │
AD8307 COM ─────────────┴─── ADS1115 AIN1 (and GND)
```

- **No series resistor.** The AD8307 OUT pin is a current output
  (2 µA/dB) into an internal 12.5kΩ resistor, so its source impedance is
  already 12.5kΩ. A series resistor adds nothing; the capacitor alone
  presents the ADS1115 sampling switch with a low impedance.
- **C: 100nF** against the 12.5kΩ source gives a corner near 130Hz
  (τ ≈ 1.3ms). That is the detector's "video bandwidth", the standard
  way of filtering a log amp output, and it removes detector ripple and
  RF pickup well before the ADC. For a meter sampled at 20Hz it is
  comfortably fast; shrink the capacitor if a faster response is ever
  wanted (10nF ≈ 1.3kHz).
- **Differential input**: AIN1 ties to the detector's ground pin so the
  ADC measures the detector output relative to its own reference, not
  relative to wherever the ADC ground happens to be on the PCB. Keep the
  AIN1 trace short.
- No TVS is needed on the analog path; it never leaves the board.

No amplification is needed: detector outputs (0.2V to 2.5V typical) are
well-matched to the ADS1115 at the ±4.096V PGA setting, giving ~20,000
counts across the signal range.

## Sensor Head: ADS1115 Configuration

| Pin | Connection |
|-----|------------|
| VDD | Head 3.3V rail, 100nF decoupling |
| ADDR | GND → I2C address 0x48 (same in every head) |
| ALERT/RDY | 10kΩ pull-up to 3.3V, otherwise unconnected |
| AIN0 | Detector output (100nF to ground at the pin) |
| AIN1 | Detector ground |
| AIN2, AIN3 | Unconnected (spare for a two-detector head) |

The firmware puts the ADC in continuous conversion mode (128 SPS, AIN0-AIN1,
±4.096V) when the head is detected and then just reads the conversion
register. The ADS1115 powers up in single-shot mode, so this is redone on
every hot-plug.

## Sensor Head: MCP9808 Temperature Sensor

| Pin | Connection |
|-----|------------|
| VDD | Head 3.3V rail, 100nF decoupling |
| A0, A1, A2 | GND → I2C address 0x18 |
| ALERT | Unconnected (open-drain, unused) |

Place the MCP9808 as close to the detector IC as possible, on the same
side of the board, with a solid ground pour connecting the two. The point
is to track the detector's temperature, not the ambient. Default
resolution (0.0625°C) is used.

## Sensor Head: EEPROM

AT24C02 (SOIC-8) or AT24CS04 (DFN-8, adds a factory serial number).
Address pins A1 and A2 must be tied to GND for address 0x50. Do not leave
them floating. WP can be tied to GND (write enabled; calibration is saved
from the SCPI interface).

## Sensor Head: RF Input

Amphenol RF 132289 SMA jack, PCB edge mount, 50Ω. Symbol
`rf_power_meter:SMA_132289` and footprint
`rf_power_meter:SMA_Amphenol_132289_EdgeMount` in the project library
(`lib/`). The footprint carries the STEP model. Place the connector on a
board edge with the pad and detector input network directly behind it;
keep the 50Ω trace to the detector short.

### 3 dB Input Pad

A 3 dB pi attenuator sits between the SMA and the detector input network:

```
SMA ──┬──[17.4Ω]──┬──── to 52.3Ω termination / coupling caps / detector
      │           │
   [294Ω]      [294Ω]
      │           │
     GND         GND
```

| Position | Ideal | E96 value | Resulting attenuation |
|----------|-------|-----------|------------------------|
| Series | 17.61Ω | 17.4Ω | 3.0 dB, return loss > 30 dB |
| Shunt (×2) | 292.4Ω | 294Ω | |

- **Why:** The pad presents the SMA with a stable 50Ω regardless of the
  detector's input impedance (the AD8307 is ~1.1kΩ with some reactance,
  and the 52.3Ω termination alone gives a mediocre match at the top of the
  band). It also raises the head's maximum input from +17 dBm to
  +20 dBm and takes the first hit from an overload or ESD event.
- **Parts:** Thin-film 1% (or better) resistors, 0805 or 0603, in a
  tight layout straight behind the SMA. Thin film keeps the attenuation
  flat to 500 MHz and stable over temperature; thick film drifts and has
  more parasitic reactance.
- **Dissipation:** At +20 dBm (100 mW) into the pad, the input shunt
  resistor dissipates ~17 mW, the series ~13 mW and the output shunt
  ~8 mW. 0603 is comfortable; 0805 gives margin for accidental
  overdrive.
- **Keep the 52.3Ω termination** after the pad. The pad is only 50Ω at
  its output when it is terminated in 50Ω. Do not merge the pad's
  output shunt and the termination into one resistor: the pad must stay a
  clean 3 dB and the detector match must stay correct at low frequency.
- **Calibration:** The pad shifts the head's effective intercept by
  +3 dB (AD8307: -84 dBm at the detector pin becomes -81 dBm at the
  SMA). Program the EEPROM `intercept` with the pad included; the
  per-frequency calibration then only has to absorb the residual
  frequency response.

### AD8307 Input Network

The AD8307 has a true differential input (INP, INM), but the standard
hookup is single-ended and "quasi-differential": signal into INP, and INM
AC-grounded through an identical capacitor so both pins see the same
source impedance and the same ground.

```
SMA ──┬──[17.4Ω]──┬──────┬──[C1 1nF]── INP (pin 8)
      │           │      │
   [294Ω]      [294Ω]  [52.3Ω]            AD8307
      │           │      │
     GND         GND    GND ─────[C2 1nF]── INM (pin 1)
                         ↑
             one ground point, right here
```

- **Both inputs must be AC-coupled.** INP and INM sit at an internal DC
  bias. Tying either pin to ground directly breaks the bias and kills
  the gain, hence the two coupling capacitors.
- **Termination before the capacitor.** The 52.3Ω sits on the connector
  side of C1 so it does not disturb the bias. At RF it is in parallel
  with the AD8307's 1.1kΩ input resistance: 52.3 ∥ 1100 = 49.9Ω. Use
  52.3Ω, not 50Ω.
- **C2 is for balance, not coupling.** The AD8307 responds to the
  difference between INP and INM. With C2 equal to C1 and grounded at the
  same point as the termination, ground and supply noise appears on both
  pins equally and cancels. Without C2, INM floats on the internal bias
  and that noise is read as signal.
- **C1 = C2 = 1nF, C0G, 0603.** The low-frequency corner is set by the
  series combination of the two capacitors against 1.1kΩ: 1nF gives
  ~290kHz, far below the 50-500MHz range. 1nF is chosen over the
  datasheet's 10nF because it stays capacitive well above the 10nF
  part's self-resonance; the meter is not intended to work in the kHz
  range.
- **Match at the top of the band.** The AD8307's ~1.4pF input
  capacitance (≈ -j227Ω at 500MHz) spoils the 50Ω match somewhat. The
  pad helps: a reflection from the detector passes through it twice, so
  return loss at the SMA improves by 6 dB over the bare detector.
- **Layout.** SMA, pad, termination node, coupling capacitors, pins, in a
  straight line. Keep R4 (52.3Ω), C1 and C2 within a few millimetres of
  each other and of the AD8307 pins, and ground R4 and C2 at the same
  via field. Nothing else should share that ground via.
- **Other AD8307 pins.** ENB tied to VPS (always on), INT and OFS left
  open (no intercept or offset adjustment needed; calibration lives in
  the EEPROM), 100nF plus a few Ω of series resistance on VPS as drawn.

## RJ45 Jacks

The cable carries DC power and I2C, so jacks with integrated magnetics
would be wrong, and LEDs have nothing to indicate. Two different
LED-less, magnetics-free, shielded 8P8C jacks are used:

**Main unit: Amphenol RJHSE-5380.** Standard through-hole right-angle
jack, 15.5 mm tall above the board. Cheap, and the main unit has the
height. Symbol `rf_power_meter:RJ45_RJHSE-5380`, footprint
`rf_power_meter:RJ45_Amphenol_RJHSE5380`.

**Sensor heads: Würth 615108150221R (WR-MJ mid-mount, tab down).**
The jack body drops through a cutout in the board edge, so it stands
only 10.65 mm above the board top and 3.25 mm below it. This is what
makes the head fit the Hammond 1455D enclosure (see below). Symbol
`rf_power_meter:RJ45_WE-615108150221R`, footprint
`rf_power_meter:RJ45_Wuerth_615108150221R_MidMount`.

Mid-mount footprint facts (drawn from the Würth datasheet, origin at the
two Ø1.8 mm board-guide holes, +y toward the board edge):

| Feature | Value |
|---------|-------|
| Signal pins | 8 × Ø0.9 hole, Ø1.35 pad, 1.02 mm pitch, two staggered rows 1.65 mm apart |
| Board guides | 2 × Ø1.8 non-plated holes, 11.9 mm apart |
| Shield clips (SH) | 2 × Ø1.2 plated holes, 16.8 mm apart, 2.05 × 3.63 mm pads |
| Board cutout | 14.75 mm wide, 11.28 mm deep from the board edge; inner end 2.92 mm from the guide holes |
| Front face | protrudes ~1.1 mm beyond the board edge |
| Reflow | THR (pin-in-paste); stencil openings 1.7 × 2.1 mm per signal pin, 120 µm stencil |

The footprint carries the cutout on `Edge.Cuts` and a reference line for
the board edge on `Dwgs.User`; align the board outline to that line. No
3D model is available in the project library yet; Würth supplies one on
request from the product page.

The shield pads (SH) go to GND at the connector on both boards.

## Sensor Head Enclosure: Hammond 1455D601BK

Extruded aluminium box, 60 mm long, 42.5 × 23.0 mm outside. Used
without the plastic bezels (they are a cosmetic snap-on trim over the
two end-plate screws; the aluminium end plates are what hold the box
together). From Hammond's drawing:

| Item | Value |
|------|-------|
| Inside height | 20.00 ± 0.42 mm |
| PCB width, slot to slot | 39.5 mm ("designed for 39 mm board") |
| PCB slots | 4 per side, 1.80 mm wide; lowest puts the board underside ≈ 2.0 mm above the floor |
| Headroom above board top, lowest slot | ≈ 16.3 mm nominal, 15.9 mm worst case |
| End plate | 42.4 × 22.9 × 1.6 mm aluminium, 2 countersunk screws on the centreline, 35.6 mm apart |

### Which PCB slot

The SMA flange hangs ~2.0 mm below the board underside, so the lowest
slot (2.0 mm above the floor) leaves it touching the floor. Use the
**second slot from the bottom**: board underside ≈ 4.05 mm above the
floor, board top ≈ 5.65 mm.

| Item | Need | Available in slot 2 |
|------|------|---------------------|
| Above board top: Würth RJ45 | 10.65 mm | 14.35 mm nominal (13.9 worst case) |
| Above board top: SMA flange | 4.3 mm | 14.35 mm |
| Below board underside: Würth RJ45 | 1.65 mm | 4.05 mm |
| Below board underside: SMA flange | 2.0 mm | 4.05 mm |

The Amphenol RJHSE-5380 at 15.5 mm would not fit in this slot, which is
why the heads use the mid-mount Würth part.

### Length budget (SMA flange and RJ45 face)

The end plates sit on the ends of the extrusion, so the inside faces of
the plates are 60.0 ± 0.5 mm apart. Two things live between the board
edges and those faces:

- **SMA end:** the Amphenol 132289 has a 1.65 mm thick flange that sits
  between the board edge and the inside of the end plate. The threaded
  barrel passes through the plate. In the KiCad footprint the board edge
  is at x = +2.54 mm (the flange's inner face line on F.Fab); the pads
  sit 2.54 mm inboard of the edge.
- **RJ45 end:** the Würth jack's front face protrudes 1.13 mm beyond the
  board edge, into the plate cutout.

```
 end plate (1.63)            extrusion 60.0 ±0.5                 end plate
 ┌──┐ 1.65 ┌──────────────────────────────────────────┐ 0.75 ┌──┐
 │  │flange│  PCB 57.6 mm                              │ gap  │  │
 │  ├──────┤ ◄─ SMA end                      RJ45 end ─►├──┐   │  │
 │  │      │                                   face ──►│  │   │  │
 └──┘      └──────────────────────────────────────────┘──┘   └──┘
```

| Item | Value |
|------|-------|
| Inside face to inside face | 60.0 ± 0.5 mm |
| SMA flange | 1.65 mm |
| PCB length | **57.6 mm** (= 60.0 − 1.65 − 0.5 tolerance − 0.25 clearance) |
| Nominal gap, RJ45-end board edge to extrusion end | 0.75 mm |
| RJ45 face position, nominal | 0.38 mm proud of the extrusion end, 1.25 mm inside the plate's outer surface |
| RJ45 face, extrusion at 59.5 / 60.5 | 0.88 proud / 0.12 inside the extrusion end; always within the plate cutout |

Nothing locates the board lengthwise except the SMA flange against its
plate, so the board can float by the 0.25-0.75 mm slack toward the RJ45
end. That only moves the SMA barrel slightly in its clearance hole and
is harmless. If you want it fixed, a dab of adhesive on the flange or a
small stop glued to the floor at the RJ45 end does it.

### End plate cutouts

Positions measured from the **bottom edge of the end plate** (the plate
is flush with the extrusion outline; the inner floor is 1.5 mm up).
With the board in slot 2 the board top is 7.15 mm above the plate's
bottom edge.

| Plate | Cutout | Centre height | Size |
|-------|--------|---------------|------|
| SMA end | round hole for the 1/4-36 barrel | ≈ 7.5 mm (board top + 0.4 mm, per the 3D model) | Ø6.5 mm |
| RJ45 end | rectangular, for the plug and tab-down latch | opening from 3.75 to 18.0 mm | 16.2 wide × 14.2 tall, corners R1 |

Both openings are centred on the plate width and clear the two
countersunk screws on the centreline (35.6 mm apart) by well over 9 mm.
Check the SMA hex body on the Amphenol drawing: if the hex sits within
1.65 mm of the flange it passes through the plate and the hole must
clear it (≈ Ø11 mm) instead of the Ø6.35 thread.

The box is anodised (insulating). If the RJ45 shield or SMA body should
be bonded to the enclosure, rely on the end-plate screw threads or
remove anodising at a contact point; do not assume the panel cutout
grounds the connector.

## Main Unit: Power Input and Port Protection

The main unit runs from a 12V, 1A AC/DC adapter. Three regulators:

```
                  ┌────────────┐
12V DC jack ──┬───┤ LM317M     ├──┬──[polyfuse 0.2A]──┬──[TVS 12V]── RJ45 #1 pin 1 (V+)
              │   │ set to 8V  │  │                   │
          [100µF] └────────────┘  └──[polyfuse 0.2A]──┼──[TVS 12V]── RJ45 #2 pin 1 (V+)
          [TVS 15V]                                  GND
              │   ┌─────────────┐
              └───┤ 5V buck     ├──┬── W5500-EVB-Pico VSYS (RP2040 + W5500)
                  │ module, 1A  │  │   ┌───────────┐
                  └─────────────┘  └───┤ 3.3V LDO  ├──── SSD1322 module
                                       │ SOT-223   │
                                       └───────────┘
```

- **Input:** 12V DC, 2.1mm jack, centre positive. Add a 100µF bulk
  capacitor and a 15V TVS (SMBJ15A) at the jack; a 12V adapter can sit
  at 12.6V, too close to a 12V part. A series Schottky or P-FET for
  reverse polarity is optional.
- **Head rail (LM317M, 8V):** an LM317MBTG (TO-220, 500mA, adjustable)
  set to 8V feeds both RJ45 ports:

  ```
  12V ──┤IN  LM317M  OUT├──┬──────────── 8V to port fuses
            ADJ           │
             │          [240Ω] R1
             ├────────────┘
           [1.3kΩ] R2        Vout = 1.25V × (1 + R2/R1) + Iadj × R2 ≈ 8.1V
             │
            GND
  ```

  0.1µF ceramic at IN, 10µF at OUT. R1 = 240Ω draws the 5mA minimum load
  the LM317 needs, so the rail stays regulated with no head plugged in.
  8V rather than 9V because the LM317 wants 2-2.5V of headroom and a 12V
  adapter can droop to 11.4V; the head's 5V LDO is happy with 8V (see
  Sensor Head: Power). Worst case dissipation is two AD8318 heads at a
  12.6V input: 4.6V × 140mA ≈ 0.65W, about a 40°C rise in a free-standing
  TO-220, so no heatsink. With two AD8307 heads it is under 0.1W. Being
  linear, it puts no switching noise on the cable.
- **Per-port fuse:** a resettable polyfuse (~200mA hold, e.g. 0ZCJ0020)
  on each RJ45 V+ pin. A shorted cable or a failed head drops that port
  only; the other channel and the main unit keep running. Hot-plugging a
  head charges its 10µF input capacitor; the polyfuse handles that
  transient without tripping.
- **5V regulator:** the Pico accepts 1.8-5.5V on VSYS. A 1A buck module
  in the 78xx footprint (Recom R-78B5.0-1.0, Traco TSR 1-2450, Murata
  OKI-78SR-5/1.5) makes 5V from 12V; a linear regulator would burn
  almost 3W here. The load is the EVB-Pico (RP2040 + W5500, ~200mA) plus
  the OLED path, ~0.4A worst case. Buck noise does not reach the heads:
  they are fed from the LM317 and have their own LDOs. If the Pico may
  be on USB while the 12V supply is on, feed VSYS through a Schottky as
  the Pico datasheet recommends.
- **3.3V budget:** the controller is a W5500-EVB-Pico. Its onboard
  regulator powers the RP2040 and the W5500 (~130mA active) and the Pico
  documentation allows about 300mA for external loads on the 3V3 pin, so
  with the W5500 already on it there is no room for a 256x64 OLED module.
  The panel voltage (VCC, 12-15V) is made by a boost converter on the
  display module, and at full brightness with a mostly-lit screen the
  module can pull 100-200mA from its 3.3V input. Give the display its own
  SOT-223 LDO (AP7361C-33 or AMS1117-3.3, ~0.35W, with 10µF on both
  sides) from the 5V rail, and leave the Pico's 3V3 pin for the pull-ups
  only. If the chosen module has a 5V input option (onboard regulator),
  feed it 5V instead and the LDO goes away.

## I2C ESD Protection

The I2C lines (SDA, SCL - RJ45 pins 3 and 4) are exposed to ESD during
cable insertion. Protect them on both ends:

```
RJ45 Pin 3 (SDA) ────────┬──── Pico GP0/GP2  /  head SDA
                         ┴
                        ───  TVS (ESDAVLC6-2BLY)
                         │
                        GND

RJ45 Pin 4 (SCL) ────────┬──── Pico GP1/GP3  /  head SCL
                         ┴
                        ───
                         │
                        GND
```

One ESDAVLC6-2BLY (dual line, SOT-23-6L, ~0.45pF per line) protects both
SDA and SCL per connector. The capacitance is negligible for 400kHz I2C
(bus limit is 400pF).

## I2C Pull-Up Resistors

I2C is open-drain and requires pull-ups. The RP2040's internal pull-ups
(~50-80kΩ) are too weak for reliable operation.

Each sensor bus runs from a Pico I2C controller straight to one RJ45
jack; there are no I2C devices in the main unit. The Ethernet cable adds
capacitance (~50-100pF/m), so pull-ups sit on both ends:

```
Main Unit:                                Sensor Head:

Pico GP0 (SDA0) ──┬── RJ45 #1 ══════════ RJ45 ──┬── ADS1115, MCP9808, EEPROM
Pico GP1 (SCL0) ──┤                             │
                  │                             │
               [10kΩ]                        [4.7kΩ]
                  │                             │
                 3.3V                          3.3V

Pico GP2 (SDA1) ──┬── RJ45 #2 ══════════ RJ45 ──┬── ADS1115, MCP9808, EEPROM
Pico GP3 (SCL1) ──┤                             │
               [10kΩ]                        [4.7kΩ]
                  │                             │
                 3.3V                          3.3V
```

- **Main unit (10kΩ):** Weaker pull-up keeps lines defined when no sensor is connected
- **Sensor head (4.7kΩ):** Stronger pull-up handles cable capacitance
- **Combined (10kΩ ∥ 4.7kΩ ≈ 3.2kΩ):** Adequate for cable length when connected

**Pull-up summary:**

| Location | Value | Quantity | Purpose |
|----------|-------|----------|---------|
| I2C0 (GP0, GP1) | 10kΩ | 2 | Keep lines defined, sensor 1 |
| I2C1 (GP2, GP3) | 10kΩ | 2 | Keep lines defined, sensor 2 |
| Sensor head (SDA, SCL) | 4.7kΩ | 2 per head | Handle cable capacitance |

## Sensor I2C Buses

The RP2040 has two hardware I2C controllers. Each is dedicated to one
sensor head:

| Controller | SDA | SCL | RJ45 |
|------------|-----|-----|------|
| I2C0 | GP0 | GP1 | #1 (channel 1) |
| I2C1 | GP2 | GP3 | #2 (channel 2) |

This replaces the TCA9548A multiplexer of the earlier design. Every head
still carries identical addresses (0x48, 0x18, 0x50); the bus it is
plugged into is what identifies the channel.

- No channel-select transaction, so steady-state reading is one 2-byte
  read per channel.
- A head yanked mid-transaction can leave a slave driving SDA low. That
  hangs only that channel's bus. Recovery is a matter of re-initialising
  the I2C controller (or clocking SCL nine times); the other channel and
  the display never see it.
- The two buses are electrically independent, so a shorted cable on one
  port does not disturb the other.

## SSD1322 OLED Display

A 256x64 4-bit grayscale OLED module with an SSD1322 controller, driven
over 4-wire SPI from the Pico's SPI1. The controller is write-only, so
only five signals are needed plus power:

```
Pico                          SSD1322 module (4-wire SPI mode)
GP10 (SPI1 SCK)  ───────────► SCLK (D0)
GP11 (SPI1 TX)   ───────────► SDIN (D1)
GP13             ───────────► CS#
GP14             ───────────► D/C#
GP15             ───────────► RES#
3.3V (LDO)       ───────────► VDD / VDDIO
GND              ───────────► GND
```

- **Interface select:** most modules pick the interface with BS0/BS1
  pins or solder jumpers. 4-wire SPI is BS0 = 0, BS1 = 0. Set this on the
  module; the firmware does not touch it.
- **Logic level:** SSD1322 VDDIO is 1.65-3.5V, so the Pico's 3.3V drives
  it directly.
- **Clock:** the SSD1322 SPI input is specified to 10 MHz (100 ns cycle).
  `config.DISPLAY_SPI_BAUD` is 10 MHz; drop it if a long ribbon cable
  causes trouble.
- **Column offset:** the controller has RAM for 480 columns; a 256-pixel
  panel normally sits at columns 0x1C-0x5B. If the image is shifted
  horizontally, adjust `config.DISPLAY_COL_OFFSET` per the module
  datasheet.
- **Panel supply:** the OLED itself needs 12-15V (VCC). Choose a module
  with the boost converter on board (e.g. the ER-OLEDM032 series, or the
  Newhaven NHD-3.12-25664 with its carrier board) so only 3.3V and logic
  come from the main board. Budget 100-200mA at full brightness.
- **Header:** 1x7 or 1x8 pin header (or the module's FPC breakout) on
  the main board; the module mounts behind the front panel.

## Presence Detect Conditioning

The head ties RJ45 pin 8 to GND. The main unit pulls the line up and
reads it on a GPIO: LOW means a head is connected.

```
                        3V3
                         │
                      [10kΩ]
                         │
RJ45 Pin 8 (DET) ────────┼────────┬──── GP2/GP3  (low = head present)
                         ┴        │
                        ───       │
                         │        │
                        GND      (RP2040 internal pull-up also enabled)
                        TVS
```

- **Pull-up (10kΩ):** The RP2040's internal pull-up (~50-80kΩ) is weak.
  An external 10kΩ gives better noise immunity when no head is
  connected, especially with long cables in an RF environment.
- **Why a ground tie:** it needs no rail in the head. A head whose
  regulator has failed still shows as present, so the firmware can
  report "head present but not responding" instead of silently showing
  an empty channel. It also keeps every voltage source off the cable
  except V+.
- **TVS:** One ESDAVLC6-2BLY per connector (one line unused, or share
  between both RJ45 presence detect lines).

## Cable Pairing

The T-568B pairs are (1,2), (3,6), (4,5) and (7,8). Each pair carries one
signal and its return: V+ with GND on (1,2), SDA with GND on (3,6), SCL
with GND on (4,5), presence detect with GND on (7,8). Pins 2, 5, 6 and 7
are all GND and must be tied together on both the main unit and every
head. Route each RJ45 GND pin to the ground pour directly at the
connector; do not daisy-chain them through a trace.

## ESD Protection Summary

**Main unit**, TVS diodes per RJ45 connector (place close to connector):

| Signals | RJ45 Pins | TVS Package | Notes |
|---------|-----------|-------------|-------|
| V+ (8V) | 1 | 1× SMF12A (12V) | After the polyfuse |
| I2C SDA + SCL | 3, 4 | 1× ESDAVLC6-2BLY | ~0.45pF OK for 400kHz |
| Presence Detect | 8 | 1× ESDAVLC6-2BLY | One line unused |

Total: 4× ESDAVLC6-2BLY plus 2× SMF12A for both RJ45 connectors (or 3×
ESDAVLC6-2BLY if the presence detect lines share one package).

**Sensor head**: 1× ESDAVLC6-2BLY on SDA/SCL and 1× SMF12A on V+, close
to the RJ45. The detector's RF input has its own protection per the
detector datasheet.

## Current Schematic Status

Both KiCad projects were started before the ADC moved into the head and
have not yet been updated:

- `main_board`: still contains two ADS1115s (U1, U2) with their RC
  filters, analog TVS diodes and ALERT pull-ups, plus the TCA9548A (U4)
  and the two I2C OLED headers (J3, J4). These all go away. RJ45 wiring
  changes: pin 1 becomes V+ (8V via polyfuse + TVS), SDA/SCL on pins
  3/4 go directly to Pico GP0/GP1 (RJ45 #1) and GP2/GP3 (RJ45 #2) with
  10kΩ pull-ups, pins 5, 6 and 7 become GND, presence detect on pin 8
  goes to GP4/GP5. Presence detect pull-downs R10/R11 become pull-ups to
  3V3. New: a header for the SSD1322 module on SPI1 (GP10, GP11,
  GP13-GP15) and a SOT-223 3.3V LDO for it from the 5V rail. The 12V
  input (jack, 100µF, 15V TVS), the LM317M 8V head rail, the 5V buck
  module and the Pico are not drawn yet.
- `sensor_heads/AD8307`: needs the ADS1115, the MCP9808, the 100nF
  output filter capacitor and the ALERT pull-up added; the detector
  output goes to AIN0 instead of RJ45 pin 4. C3/C4 (input coupling)
  change from 10nF to 1nF C0G. RJ45 wiring changes: pin 1 becomes V+ into
  a 3.3V LDO (plus 10µF and TVS), SCL moves from pin 6 to pin 4, pins 5,
  6 and 7 become GND (R6, the AGND link, goes away), pin 8 goes to GND
  instead of 3V3. The +3V3 and +5V power symbols now mean the head's own
  LDO outputs. The 3 dB pi pad (17.4Ω series, 2× 294Ω
  shunt) goes between J1 and the 52.3Ω termination R4. EEPROM A1/A2 must
  be tied to GND. The TVS symbol is still the superseded PESD5V0L2BT-Q
  with a SOT-23-5 footprint and should become ESDAVLC6-2BLY (SOT-23-6L).
