# Front Panel Controller
# Rotary encoder + push switch for manual entry of frequency and external
# attenuator. SCPI always wins: a remote write to either value drops the
# panel back to the measurement view, and SYSTem:KLOCk disables the
# encoder entirely until unlocked or power cycled.

import time

from .encoder import RotaryEncoder, PushButton
import config

FIELD_FREQUENCY = "freq"
FIELD_ATTENUATOR = "atten"
_FIELD_ORDER = (FIELD_FREQUENCY, FIELD_ATTENUATOR)


def _field_key(field):
    """Sort key: (channel, position in the edit cycle)."""
    return (field[0], _FIELD_ORDER.index(field[1]))


class FrontPanel:
    """
    Front panel state machine.

    States:
        measurement: encoder rotation ignored, short press enters editing
        editing:     (channel, field) is highlighted on the display;
                     rotation changes it, short press moves to the next
                     field, a press after the last field or 5 s of idle
                     returns to measurement
    """

    def __init__(self, meter, encoder=None, button=None):
        """
        Args:
            meter: PowerMeter instance
            encoder: RotaryEncoder, or None to create one from config
            button: PushButton, or None to create one from config
        """
        self.meter = meter
        self.encoder = encoder or RotaryEncoder(
            config.ENCODER_A, config.ENCODER_B, reverse=config.ENCODER_REVERSE)
        self.button = button or PushButton(
            config.ENCODER_SW, active_high=config.ENCODER_SW_ACTIVE_HIGH)

        self.locked = False          # Always powers up unlocked
        self.edit = None             # (channel, field) or None
        self._last_activity = time.ticks_ms()

    # --- External control --------------------------------------------

    def set_locked(self, locked):
        """Lock or unlock manual entry (SYSTem:KLOCk)."""
        self.locked = bool(locked)
        if self.locked:
            self.edit = None

    def cancel_edit(self):
        """Leave edit mode, e.g. because SCPI just wrote a value."""
        self.edit = None

    def is_editing(self):
        return self.edit is not None

    # --- Field list -------------------------------------------------------

    def _fields(self):
        """Ordered list of editable (channel, field) pairs right now."""
        fields = []
        for ch in sorted(self.meter.channels):
            channel = self.meter.channels[ch]
            if channel.get_frequencies():
                fields.append((ch, FIELD_FREQUENCY))
            fields.append((ch, FIELD_ATTENUATOR))
        return fields

    def _next_field(self):
        """Advance to the next field; None after the last one."""
        fields = self._fields()
        if not fields:
            return None
        if self.edit is None:
            return fields[0]
        # Next field in cycle order. Works even if the current field has
        # vanished (head unplugged while editing its frequency).
        current = _field_key(self.edit)
        for f in fields:
            if _field_key(f) > current:
                return f
        return None

    # --- Value changes ----------------------------------------------------

    def _apply_delta(self, delta):
        ch, field = self.edit
        channel = self.meter.get_channel(ch)
        if channel is None:
            return

        if field == FIELD_FREQUENCY:
            # The panel steps through the calibration points only. If SCPI
            # left the frequency between two points, the first click lands
            # on the neighbouring point in the direction of rotation.
            freqs = channel.get_frequencies()
            if not freqs:
                return
            current = channel.get_frequency()
            if current in freqs:
                idx = freqs.index(current) + delta
            else:
                above = [i for i, f in enumerate(freqs) if f > current]
                first_above = above[0] if above else len(freqs)
                # delta > 0: first point above, then onwards; delta < 0:
                # first point below, then downwards
                idx = first_above + delta - 1 if delta > 0 else first_above + delta
            idx = max(0, min(len(freqs) - 1, idx))
            channel.set_frequency(freqs[idx])

        elif field == FIELD_ATTENUATOR:
            value = round(channel.get_attenuator() + delta * config.UI_ATTEN_STEP_DB)
            value = max(0, min(config.UI_ATTEN_MAX_DB, value))
            channel.set_attenuator(value)

    # --- Main loop hook ---------------------------------------------------

    def poll(self):
        """
        Process encoder input. Call periodically (config.UI_POLL_MS).

        Returns True if the display should be refreshed right away.
        """
        delta = self.encoder.get_delta()
        presses = self.button.get_presses()
        now = time.ticks_ms()

        if self.locked:
            # Input is discarded while remote-locked
            self.edit = None
            return False

        changed = False

        for _ in range(presses):
            self.edit = self._next_field()
            self._last_activity = now
            changed = True

        if delta and self.edit is not None:
            self._apply_delta(delta)
            self._last_activity = now
            changed = True

        if self.edit is not None and \
                time.ticks_diff(now, self._last_activity) > config.UI_EDIT_TIMEOUT_MS:
            self.edit = None
            changed = True

        return changed
