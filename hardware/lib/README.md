# Project KiCad Library

Project-local symbols, footprints and 3D models that are not in the
standard KiCad libraries, or that we want pinned to a specific part.

| Path | Contents |
|------|----------|
| `rf_power_meter.kicad_sym` | Symbols, each with footprint, datasheet, manufacturer and MPN fields filled in. |
| `rf_power_meter.pretty/` | Footprints, copied from KiCad's libraries with the 3D model path made project-relative. |
| `3dmodels/` | STEP models referenced by the footprints. |

## Parts

| Symbol | Footprint | 3D model | Part |
|--------|-----------|----------|------|
| `SMA_132289` | `SMA_Amphenol_132289_EdgeMount` | `SMA_Amphenol_132289_EdgeMount.step` | Amphenol RF 132289, SMA jack, 50Ω, PCB edge mount. RF input on every head. |
| `RJ45_RJHSE-5380` | `RJ45_Amphenol_RJHSE5380` | `RJ45_Amphenol_RJHSE538X.step` (see note) | Amphenol RJHSE-5380, RJ45 8P8C jack, shielded, through hole, no magnetics, no LEDs. Main-unit ports. |
| `RJ45_WE-615108150221R` | `RJ45_Wuerth_615108150221R_MidMount` | none yet | Würth WR-MJ 615108150221R, RJ45 8P8C, mid-mount in a board-edge cutout, shielded, tab down, THR, no magnetics, no LEDs. Sensor heads. Footprint drawn from the datasheet (not vendor-supplied); verify against a sample before ordering boards. |

**SMA footprint note:** the board edge belongs at x = +2.54 mm in the
footprint's frame (the F.Fab line where the slotted body ends and the
1.65 mm flange begins). The flange then sits outside the board, between
the edge and the enclosure end plate; see the enclosure section in
`../README.md`.

**RJ45 model note:** KiCad has no model for the LED-less RJHSE-5380, only
for the RJHSE-538X LED variants. The housing and pin positions are the
same, so the 538X model is used as a stand-in. It shows two LED windows
the real part does not have. Replace it with Amphenol's own STEP for the
RJHSE-5380 if exact appearance matters.

**Mid-mount RJ45 note:** the shield pads sit flush against the board
cutout, exactly as the Würth drawing specifies, so KiCad's default
0.5 mm copper-to-edge DRC rule flags two violations on them. Add a DRC
exclusion for those two pads (or relax the rule for that footprint)
rather than shrinking the pads.

## How it is wired in

Each KiCad project directory (`main_board/`, `sensor_heads/<head>/`) has a
`sym-lib-table` and `fp-lib-table` registering this library under the
nickname `rf_power_meter`, using `${KIPRJMOD}`-relative paths.

3D model paths inside the footprints use `${RFPM_LIB}/3dmodels/...`.
`RFPM_LIB` is a project text variable defined in each `.kicad_pro`
(Project Settings → Text Variables) and points at this directory relative
to that project:

| Project | `RFPM_LIB` |
|---------|------------|
| `main_board/` | `${KIPRJMOD}/../lib` |
| `sensor_heads/<head>/` | `${KIPRJMOD}/../../lib` |

KiCad expands the nested `${KIPRJMOD}` (verified with `kicad-cli pcb
export step` from both depths), so one footprint file serves projects at
any depth. Nothing needs to be configured globally; cloning the repo is
enough.

## Adding a new head project

Copy `sensor_heads/AD8307/sym-lib-table` and `fp-lib-table` into the new
project directory and add the `RFPM_LIB` text variable to its
`.kicad_pro`. Use `rf_power_meter:SMA_132289` for the RF input and
`rf_power_meter:RJ45_WE-615108150221R` for the cable jack.
