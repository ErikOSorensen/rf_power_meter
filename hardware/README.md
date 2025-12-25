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
