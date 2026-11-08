# Hardware Design

KiCad project files for the RF Power Meter.

## Directory Structure

- `main_board/` - Main unit PCB: Pico, W5500, SSD1322 OLED header, encoder debounce, RJ45 jacks
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
             │                     └──────────┘ [10µF]       3.3V detector
            GND                                  │
                                                GND
```

- **3.3V LDO: LP2985-33 (SOT-23-5).** Low-noise, 16V input, 150mA. This
  rail feeds the ADC, so noise matters more than efficiency; a buck
  converter is not appropriate here. Capacitors per the datasheet, all
  ceramic (the current LP2985 is stable with ceramics, ESR window ≈ 5mΩ
  to 3Ω):

  | Pin | Capacitor | Notes |
  |-----|-----------|-------|
  | VIN | 1µF, 25V X7R (C9) | Right at the pin. The 10µF/TVS at the RJ45 is the bulk; if it sits within ~1cm of the regulator it can serve as the input capacitor alone. |
  | VOUT | 10µF/25V tantalum (C11, as drawn) or 10µF 10V X7R | Datasheet minimum is 2.2µF; 10µF stiffens the rail against the AD8307's signal-dependent supply current. Up to 100µF is allowed. |
  | BYPASS | 10nF C0G (C10) | Cuts bandgap noise by ~10×. Slows start-up to a few ms, which is irrelevant here. |
  | ON/OFF | tie to VIN | Must not float. |

  MIC5205-3.3 is a pin-compatible fallback with the same capacitor
  values.
- **5V LDO (5V-detector heads only):** AP7361C-50 or LD1117S50 in SOT-223.
  The 3.3V LDO then takes its input from the 5V rail, so the hot part is
  the SOT-223 and the 3.3V regulator sees only ~1.7V across it.
- **3.3V-detector heads:** omit the 5V LDO, feed the 3.3V LDO from V+.
- **Input protection:** 10µF/25V tantalum (C8; a 25V X7R ceramic also works) and a
  12V TVS (SMF12A, D2) on V+ at the RJ45. The RJ45 is keyed, so reverse polarity
  protection is optional; a Schottky in series costs 0.3V of headroom if
  wanted.
- **Outputs:** 10µF on the 3.3V LDO output (see above), 10µF on the 5V
  LDO output, plus 100nF at every IC.

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
| AIN2, AIN3 | GND (unused inputs tied low; a two-detector head would free them) |

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

AT24CS04-SSHM (SOIC-8, 4 kbit, with a factory 128-bit serial number).
A1 and A2 are tied to GND for address 0x50 (0x51 answers for the upper
256 bytes; the serial number block answers at 0x58, word addresses
0x80-0x8F). Do not leave the address pins floating: they have no
internal pull-downs. WP (pin 7) is tied to GND, write enabled, since
calibration is saved from the SCPI interface. Pin 1 (NC) is left open.
The UDFN variant (AT24CS04-MAHM) has the same pinout plus an exposed
pad, which may be grounded or left floating.

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
SMA ──┬──[17.6Ω]──┬──── to 52.3Ω termination / coupling caps / detector
      │           │
   [294Ω]      [294Ω]
      │           │
     GND         GND
```

| Position | Ideal | Chosen value | Resulting attenuation |
|----------|-------|-----------|------------------------|
| Series | 17.61Ω | 17.6Ω (R2 as drawn, E192; 17.4Ω E96 is equally fine) | 3.0 dB, return loss > 30 dB |
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
SMA ──┬──[17.6Ω]──┬──────┬──[C1 10nF]─ INP (pin 8)
      │           │      │
   [294Ω]      [294Ω]  [52.3Ω]            AD8307
      │           │      │
     GND         GND    GND ─────[C2 10nF]─ INM (pin 1)
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
- **C1 = C2 = 10nF, C0G, 0603.** This is the datasheet value. The
  low-frequency corner is set by the series combination of the two
  capacitors against 1.1kΩ: 10nF gives ~30kHz, far below the 50-500MHz
  range. A 0603 10nF self-resonates around 65MHz and is inductive above
  that, but with ~0.6nH of parasitic inductance it is still only ~2Ω at
  500MHz, in series with the detector's 1.1kΩ. 1nF would work equally
  well (~3Ω at 50MHz, ~2Ω at 500MHz, corner ~290kHz); the match at the
  top of the band is set by the AD8307's input capacitance, not by the
  coupling capacitors. What matters is that C1 and C2 are identical in
  value, dielectric and footprint.
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
low above the board (10.65 mm per the datasheet figures used in the
enclosure budget below; Würth's STEP model shows only 7.5 mm) and about
3 mm below it. This is what
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
| Front face | protrudes ~1.1 mm beyond the board edge per the datasheet drawing; the vendor STEP shows 2.3 mm (see `lib/README.md`) |
| Reflow | THR (pin-in-paste); stencil openings 1.7 × 2.1 mm per signal pin, 120 µm stencil |

The footprint carries the cutout on `Edge.Cuts` and a reference line for
the board edge on `Dwgs.User`; align the board outline to that line. Würth's
STEP model is in `lib/3dmodels/` and attached to the footprint; the
placement transform is documented in `lib/README.md`.

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

## Sensor Head PCB: Dimensions and Stack-up

From the enclosure budget above:

| Item | Value | Why |
|------|-------|-----|
| Length | 57.6 mm | 60.0 mm between end plate inner faces, minus the 1.65 mm SMA flange, 0.5 mm extrusion tolerance and 0.25 mm clearance |
| Width | 39.0 mm | Slot to slot is 39.5 mm; Hammond designs the extrusion for a 39 mm board, 0.25 mm per side |
| Thickness | 1.6 mm | Slots are 1.8 mm wide. The Amphenol edge-mount SMA and the Würth mid-mount RJ45 are both specified for 1.6 mm boards |
| Slot | second from the bottom | See "Which PCB slot" |
| Corners | square along the long edges | The edges ride in the slots for the full length |

Keep-outs:

- **Long edges:** ~1.5 mm of each edge sits inside the slot. No
  components there, and no copper either: the anodising is thin at the
  slot and a scratched edge could short to the box.
- **SMA end:** the board edge is the footprint's F.Fab line, pads
  2.54 mm inboard. Nothing may extend past the edge; the flange sits
  between edge and plate.
- **RJ45 end:** only the Würth jack's face (1.13 mm) protrudes past the
  edge.
- **Height:** top side up to ~14 mm (only the RJ45 approaches this),
  underside up to ~3 mm (SMD passives are fine, nothing tall).

### Four layers

The head is built as a **4-layer board**, standard 1.6 mm stack-up,
layer 2 solid ground, layer 3 ground (or 3.3V), all routing on layers
1 and 4. At 500 MHz the wavelength in FR4 is ~300 mm and the RF path
from SMA pad to AD8307 pin is under 10 mm, so transmission-line effects
are small either way; the reasons for four layers are elsewhere:

- **An unbroken ground under everything.** On a 39 × 58 mm two-layer
  board with five ICs and I2C routed around, some traces end up on the
  bottom and each one slots the ground. With four layers the plane
  under the ADC, the detector's COM pin and the input network stays
  whole without policing.
- **A real 50Ω trace.** With ~0.2 mm prepreg between layers 1 and 2 a
  50Ω microstrip is ~0.35 mm wide, matching an 0603 pad. On 1.6 mm
  two-layer it is ~2.9 mm, impossible in a 10 mm run full of 0603
  parts. The two-layer alternative (a ~0.5 mm, ~100Ω trace, ~12
  electrical degrees at 500 MHz) gives ~16 dB return loss and ~0.1 dB
  of ripple at the detector, halved at the SMA by the pad and absorbed
  by the per-frequency calibration, so it would work, but it is a
  compromise the extra layers remove for a few euros per batch.
- **Separated return currents.** I2C and ADC digital edges return on
  the plane under their own traces, away from the input network, with
  no via fences needed.

If a head is ever made on two layers: keep the entire bottom layer
under the RF section as unbroken ground, route I2C only on the top, and
keep the SMA-to-C1 run under 5 mm.

## Main Unit: Power Input and Port Protection

The main unit runs from a 12V, 1A AC/DC adapter. Three regulators:

```
                            ┌────────────┐
12V ──[SS14 D5]──┬──────────┤ LM317      ├──┬──[SMF12A D2]── RJ45 #1 pin 1 (V+)
 screw terminal  │          │ SOT-223 8V │  │
 J5          [2×100µF]      └────────────┘  └──[SMF12A D3]── RJ45 #2 pin 1 (V+)
             [1µF] [100nF]
                 │          ┌──────────────┐
                 └──────────┤ R-78C5.0-1.0 ├──┬──[SS14 D1]── W5500-EVB-Pico VSYS
                            │ 5V buck, 1A  │  │   ┌─────────────┐
                            └──────────────┘  └───┤ AP7361C-33  ├──── SSD1322 module
                                                  │ SOT-223     │     (3.3V, J1 pin 2)
                                                  └─────────────┘
```

- **Input:** 12V DC on a 2-pole 5.08 mm screw terminal (J5, Phoenix
  MKDS 1,5/2). A series SS14 Schottky (D5) gives reverse-polarity
  protection at the cost of ~0.35V. Bulk capacitance is 2× 100µF/25V
  electrolytic (C8, C10) plus 1µF tantalum (C9) and 100nF (C4). No input
  TVS is fitted in the current schematic; a 15V SMBJ15A across the input
  would be a cheap addition (a 12V adapter can sit at 12.6V, too close
  for a 12V part).
- **Head rail (LM317, 8V):** an LM317 in SOT-223 (U5) set to 8V feeds
  both RJ45 ports:

  ```
  12V ──┤IN  LM317   OUT├──┬──────────── 8V to the port TVS diodes
            ADJ           │
             │          [240Ω] R1
             ├────────────┘
           [1.3kΩ] R2        Vout = 1.25V × (1 + R2/R1) + Iadj × R2 ≈ 8.1V
             │
            GND
  ```

  100nF ceramic at IN (the input bank), 1µF tantalum (C3) at OUT: the
  LM317 wants at least 1µF with some ESR there, so keep it tantalum
  rather than a bare ceramic. R1 = 240Ω draws the 5mA minimum load
  the LM317 needs, so the rail stays regulated with no head plugged in.
  8V rather than 9V because the LM317 wants 2-2.5V of headroom and a 12V
  adapter can droop to 11.4V; the head's 5V LDO is happy with 8V (see
  Sensor Head: Power). Worst case dissipation is two AD8318 heads at a
  12.6V input: 4.6V × 140mA ≈ 0.65W, about a 40°C rise for a SOT-223 on
  a few cm² of copper pour, so no heatsink. With two AD8307 heads it is under 0.1W. Being
  linear, it puts no switching noise on the cable.
- **Per-port fuse: not fitted.** The schematic takes the 8V rail straight
  to each RJ45 pin 1 with only the SMF12A TVS (D2, D3). A resettable
  polyfuse (~200mA hold, e.g. 0ZCJ0020) per port would let a shorted
  cable or failed head drop only its own channel; as drawn, a short
  pulls the LM317 into current limit and both heads lose power until the
  fault is removed. Hot-plug inrush into a head's 10µF would not trip
  such a fuse. Add them in the next revision or accept the behaviour.
- **5V regulator:** the Pico accepts 1.8-5.5V on VSYS. A Recom
  R-78C5.0-1.0 (1A buck module, SIP-3, 78xx pinout, 8-42V input) makes
  5V from 12V; a linear regulator would burn almost 3W here. Traco
  TSR 1-2450 or Recom R-78B5.0-1.0 drop into the same footprint. Put
  the input and output capacitors from the R-78C datasheet right at the
  module pins; the 100µF at the jack does not replace them. The load is the EVB-Pico (RP2040 + W5500, ~200mA) plus
  the OLED path, ~0.4A worst case. Buck noise does not reach the heads:
  they are fed from the LM317 and have their own LDOs. 10µF tantalum at
  the module input and output (C11, C13). VSYS is fed through an SS14
  (D1), as the Pico datasheet recommends, so a USB cable can be plugged
  in while the 12V supply is on.
- **3.3V budget:** the controller is a W5500-EVB-Pico. Its onboard
  regulator powers the RP2040 and the W5500 (~130mA active) and the Pico
  documentation allows about 300mA for external loads on the 3V3 pin, so
  with the W5500 already on it there is no room for a 256x64 OLED module.
  The panel voltage (VCC, 12-15V) is made by a boost converter on the
  display module, and at full brightness with a mostly-lit screen the
  module can pull 100-200mA from its 3.3V input. The display therefore
  has its own AP7361C-33 (U7, SOT-223, ~0.35W, stable with any capacitor
  type) from the 5V rail, with 10µF tantalum on the input (C13) and
  output (C12) plus 47µF/10V tantalum bulk (C1) on the output. The
  Pico's 3V3 pin carries only the pull-ups and the 74HC14.

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
- **Header:** 2x8 box header J1 (2.54 mm, IDC) on the main board,
  wired pin-for-pin over a 16-way ribbon to the module's 2x8 pin strip
  (both numbered odd/even across the rows, so conductor N is pin N at
  both ends). Angled Würth WR-BHD 61201621721 on the board, 61201623021
  sockets on the cable; the schematic footprint is still the vertical
  IDC header and should become the horizontal one. The module's pin
  order follows the ER-OLEDM032 family and was checked with a meter
  (pin 1 GND, pin 2 VDD, pin 3 open, pins 4-16 controller inputs, no
  pull-ups on the module):

  | J1 pin | Signal |
  |--------|--------|
  | 1 | GND |
  | 2 | +3.3V from the display LDO |
  | 3 | NC |
  | 4 | SCLK, GP10 |
  | 5 | SDIN, GP11 |
  | 6 | D2, left open (unused in 4-wire SPI) |
  | 7-13 | GND (D3-D7, E/RD#, R/W# tied low) |
  | 14 | D/C#, GP14 |
  | 15 | RES#, GP15, 10kΩ pull-up to 3V3 (R9) |
  | 16 | CS#, GP13, 10kΩ pull-up to 3V3 (R12) |

  The pull-ups hold the panel in reset and deselected while the Pico
  boots. Mark pin 1 on the module and glue the socket once the mapping
  has been verified; the pin strip has no shroud or key.

## Rotary Encoder and Debouncing

A rotary encoder with push switch on the front panel sets frequency
and external attenuator. All three contacts are debounced in hardware: an RC filter
followed by a 74HC14 Schmitt inverter, so the Pico only ever sees one
clean edge per contact change and the firmware uses plain edge
interrupts with no debounce timers.

> **Schematic note:** the main board schematic currently places a
> PEC12R-2217F-S0024 (U4, the part available in the personal library).
> The hookup below is identical for both parts (A/B/C quadrature, D/E
> switch); the PEC16 is specified for its panel bushing. Resolve before
> layout.

**Part: Bourns PEC16-2215F-S0024.** 16 mm encoder, 24 detents, 24
pulses per revolution, push switch, 15 mm insulated flatted shaft (6 mm
diameter). Terminal code 2 is "PC pin vertical / down facing": the
pins go straight down into the board and the shaft runs parallel to it,
pointing forward through the front panel. An M9 × 0.75 threaded bushing
with the supplied nut and washer fastens the encoder to the panel, so
the panel takes the turning and push forces instead of the solder
joints.

- **Board position:** solder it at the front edge of the main board,
  shaft forward. The shaft centre sits 12.5 mm above the board surface;
  set the panel hole height from that.
- **Panel cutout:** Ø9.3 mm for the bushing plus a Ø3.3 mm hole for the
  anti-rotation tab, 9.0 mm from the bushing centre (Bourns "Panel Hole
  Detail"). The 15 mm shaft has a 5 mm bushing, which leaves room for
  the 2 mm nut on a panel up to about 2.5 mm thick.
- **Pulses vs detents:** 24 pulses on 24 detents is one full quadrature
  cycle per click, which is what `config.ENCODER_STEPS_PER_DETENT = 4`
  assumes. A 12-pulse/24-detent part would need it set to 2.
- **Why not PEC11R or PEC12R:** the side-facing PEC11R-1/2 versions with a
  bushing are not stocked at 24 pulses, and the side-facing PEC12R-2 has
  no bushing at all. The shaft-up PEC11R-4xxx would need its own board
  behind the panel.

```
                 R1              R2
3V3 ────────────[10kΩ]────┬─────[10kΩ]─────┬──────┤>o────── GP6 (A)
                          │                │     74HC14
                     encoder A           [10nF]
                       contact             │
                          │                │
                         GND              GND

(identical for B → GP7; the switch → GP8 uses 470nF instead of 10nF)
```

| Signal | Encoder pin | Filter | 74HC14 | Pico |
|--------|-------------|--------|--------|------|
| A | A | 10kΩ + 10kΩ + 10nF | 1A → 1Y | GP6 |
| B | B | 10kΩ + 10kΩ + 10nF | 2A → 2Y | GP7 |
| Switch | D | 10kΩ + 10kΩ + 470nF | 3A → 3Y | GP8 |
| Common | C, E | GND | | |

- **RC values, A and B (10nF):** R1 pulls the contact up, R2 and C form
  the filter. The time constant is 100µs when the contact closes
  (discharge through R2 alone) and 200µs when it opens (charge through
  R1 + R2). This is the network Bourns recommends for its PEC encoders.
  It does not swallow the datasheet's worst-case 5ms of bounce and does
  not need to: a bounce on one channel only toggles between two adjacent
  quadrature states, so the decoder counts +1, -1 and nets zero. What
  the filter must not do is eat real edges. Even at an unrealistic 5
  turns per second a 24-detent encoder gives 8.3ms per detent, so edges
  on one channel are at least 4ms apart, and the 74HC14 threshold is
  reached in about 0.8 rising time constants, 160µs. 47nF would still be
  fine; 100nF starts to skew the A/B timing.
- **RC value, switch (470nF, C7):** 4.7ms / 9.4ms time constants. The
  press handler counts every rising edge with no software lockout, so
  this filter must swallow the full 5ms bounce. A press registers about
  5ms after contact, invisible to the user, and no finger repeats faster
  than 100ms.
- **74HC14:** runs from 3V3 with a 100nF decoupling capacitor. Its
  hysteresis (~0.9V at 3.3V) turns the slow RC ramp into a single sharp
  transition, so there are no double interrupts. Tie the three unused
  inputs (4A, 5A, 6A) to GND and leave their outputs open.
- **Inversion:** the inverter makes a closed contact read HIGH. The
  quadrature direction is unaffected (both channels are inverted
  together) and the switch polarity is set by
  `config.ENCODER_SW_ACTIVE_HIGH = True`. If clockwise turns the wrong
  way, set `config.ENCODER_REVERSE` rather than swapping wires.
- **Placement:** the encoder and its RC filters and 74HC14 are all on
  the main board, so there is no panel wiring. Keep the filter close to
  the encoder pins; the 74HC14 also buffers the Pico from ESD that a
  hand on the knob couples into the contacts.
- **Pico side:** the RP2040 pads have their own Schmitt input stage, so
  the RC filter alone would usually work. The 74HC14 is cheap insurance
  for a panel control that gets handled constantly.

## Presence Detect Conditioning

The head ties RJ45 pin 8 to GND. The main unit pulls the line up and
reads it on a GPIO: LOW means a head is connected.

```
                        3V3
                         │
                      [10kΩ]
                         │
RJ45 Pin 8 (DET) ────────┼────────┬──── GP4/GP5  (low = head present)
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
| V+ (8V) | 1 | 1× SMF12A (12V) | D2, D3; no polyfuse fitted |
| I2C SDA + SCL | 3, 4 | 1× ESDAVLC6-2BLY | ~0.45pF OK for 400kHz |
| Presence Detect | 8 | 1× ESDAVLC6-2BLY | One line unused |

Total: 4× ESDAVLC6-2BLY plus 2× SMF12A for both RJ45 connectors (or 3×
ESDAVLC6-2BLY if the presence detect lines share one package).

**Sensor head**: 1× ESDAVLC6-2BLY on SDA/SCL and 1× SMF12A on V+, close
to the RJ45. The detector's RF input has its own protection per the
detector datasheet.

## Current Schematic Status

Both schematics now follow the design above. Remaining differences and
open items:

- `main_board` (schematic drawn; PCB layout not started):
  - Power as drawn: screw terminal J5 → SS14 (D5) → 12V bank (2× 100µF,
    1µF, 100nF) → LM317 SOT-223 (U5, 240Ω/1.3kΩ, 1µF tantalum out) → 8V
    with SMF12A (D2, D3) at each RJ45 pin 1. R-78C5.0-1.0 (U2, 10µF in
    and out) → 5V → SS14 (D1) → Pico VSYS; AP7361C-33 (U7, 10µF + 47µF
    out) → display 3.3V on J1 pin 2.
  - Not drawn: the per-port polyfuses and the 15V input TVS discussed
    above. Add them or formally drop them.
  - Encoder is a PEC12R-2217F-S0024 (U4), not the PEC16-2215F-S0024 the
    encoder section specifies. Same wiring; decide on the part.
  - OLED header J1 uses the vertical IDC footprint; change to the
    horizontal footprint for the angled Würth 61201621721.
  - Pico pin assignment, I2C pull-ups (10kΩ), presence pull-ups (10kΩ),
    ESD (ESDAVLC6-2BLY D4/D7 on I2C, D8/D9 on presence with one line
    unused) and the 74HC14 debounce (10nF/10nF/470nF) match the sections
    above.
- `sensor_heads/AD8307` (schematic complete; 4-layer layout in progress):
  - References: U1 AT24CS04-SSHM, U2 MCP9808, U3 AD8307, U4 ADS1115,
    U5 LP2985-3.3, J1 SMA, J2 RJ45, D1 ESDAVLC6-2BLY, D2 SMF12A.
  - Schematic matches the sections above: LP2985-3.3 (U5) with 1µF (C9)
    in, 10nF (C10) bypass and 10µF/25V tantalum (C11) out; 10µF/25V
    tantalum (C8) and SMF12A (D2) on V+; AD8307 with the 3 dB pad
    (17.6Ω/2× 294Ω), 52.3Ω termination and 10nF coupling; ADS1115 (ADDR
    and AIN1-AIN3 → GND, 10kΩ on ALERT/RDY, 100nF on AIN0); MCP9808 MSOP
    (A0-A2 → GND); AT24CS04-SSHM (A1, A2, WP → GND); 4.7kΩ pull-ups;
    ESDAVLC6-2BLY (D1) on SDA/SCL.
  - Layout: 57.6 × 39.0 mm outline with the RJ45 notch, SMA and RJ45 on
    the board centreline, GND zone on F.Cu, In1.Cu and B.Cu, +3V3 zone
    on In2.Cu, rule area voiding In1.Cu under the SMA pin pad. Net
    classes: RF (0.35 mm, no vias, 0.6 mm pour clearance) and power
    (VCC, +3V3: 0.5 mm, with a 0.2 mm neck-down allowed inside the U3,
    U4 and U6 courtyards); custom rules in `AD8307.kicad_dru`.
    Silkscreen carries the I2C address table and the head label on the
    top and the RJ45 pinout on the bottom. Remaining DRC: one starved
    thermal (J2 pin 5), one clearance and one hole-clearance item, the
    J1/J2 edge items, and one unrouted connection.
