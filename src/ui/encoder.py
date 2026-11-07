# Rotary Encoder Driver
# Quadrature decoding with edge interrupts. Expects hardware-debounced
# inputs (RC filter + Schmitt trigger), so there is no software debounce.

from machine import Pin, disable_irq, enable_irq
import config

# Transition table indexed by (old_state << 2) | new_state, where state is
# (A << 1) | B. +1 and -1 are valid steps, 0 is no change or an invalid
# jump (both lines changed at once).
_TRANSITIONS = (
     0, -1, +1,  0,
    +1,  0,  0, -1,
    -1,  0,  0, +1,
     0, +1, -1,  0,
)


class RotaryEncoder:
    """
    Incremental rotary encoder, one step per detent.

    The decoder counts every quadrature transition and reports a step
    whenever a full detent's worth (config.ENCODER_STEPS_PER_DETENT) has
    accumulated in one direction. Steps are collected in the IRQ handler
    and consumed with get_delta() from the main loop.
    """

    def __init__(self, pin_a, pin_b, reverse=False,
                 steps_per_detent=config.ENCODER_STEPS_PER_DETENT):
        self._a = Pin(pin_a, Pin.IN)
        self._b = Pin(pin_b, Pin.IN)
        self._reverse = reverse
        self._steps_per_detent = steps_per_detent
        self._state = self._read_state()
        self._accum = 0     # Transitions since last detent
        self._delta = 0     # Detents since last get_delta()

        self._a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._irq)
        self._b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._irq)

    def _read_state(self):
        return (self._a.value() << 1) | self._b.value()

    def _irq(self, pin):
        new_state = self._read_state()
        step = _TRANSITIONS[(self._state << 2) | new_state]
        self._state = new_state
        if step == 0:
            return
        self._accum += step
        if self._accum >= self._steps_per_detent:
            self._accum = 0
            self._delta += -1 if self._reverse else 1
        elif self._accum <= -self._steps_per_detent:
            self._accum = 0
            self._delta += 1 if self._reverse else -1

    def get_delta(self):
        """Return detents turned since the last call (positive = clockwise)."""
        irq_state = disable_irq()
        delta = self._delta
        self._delta = 0
        enable_irq(irq_state)
        return delta


class PushButton:
    """
    Momentary push button on a hardware-debounced input.

    Press events are counted in the IRQ handler and consumed with
    get_presses().
    """

    def __init__(self, pin, active_high=True):
        self._pin = Pin(pin, Pin.IN)
        self._active_high = active_high
        self._presses = 0
        trigger = Pin.IRQ_RISING if active_high else Pin.IRQ_FALLING
        self._pin.irq(trigger=trigger, handler=self._irq)

    def _irq(self, pin):
        self._presses += 1

    def is_pressed(self):
        """Current button state."""
        return bool(self._pin.value()) == self._active_high

    def get_presses(self):
        """Return the number of presses since the last call."""
        n = self._presses
        self._presses = 0
        return n
