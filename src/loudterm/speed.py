"""Playback speed rules for the TTS engine.

Kokoro accepts a `speed` multiplier where 1.0 is the natural pace. Values far
outside this range distort the voice, so everything is clamped here.
"""

MIN_SPEED = 0.5
MAX_SPEED = 2.0
DEFAULT_SPEED = 1.0
SPEED_STEP = 0.1

RESET_KEYWORDS = ("reset", "default", "normal")


def clamp_speed(speed: float) -> float:
    return round(min(max(speed, MIN_SPEED), MAX_SPEED), 2)


def adjust_speed(current: float, delta: float) -> float:
    """Return `current` shifted by `delta`, clamped to the valid range."""
    return clamp_speed(current + delta)


def faster(current: float, step: float = SPEED_STEP) -> float:
    return adjust_speed(current, step)


def slower(current: float, step: float = SPEED_STEP) -> float:
    return adjust_speed(current, -step)


def parse_speed_arg(arg: str, current: float) -> float | None:
    """Resolve a `/speed` argument into a new speed value.

    Accepts an absolute value (`1.5`), a relative one (`+0.2`, `-0.1`), a bare
    `+`/`-` for a single step, or a reset keyword. Returns None when the
    argument cannot be understood.
    """
    arg = arg.strip().lower()

    if not arg:
        return current

    if arg in RESET_KEYWORDS:
        return DEFAULT_SPEED

    if arg == "+":
        return faster(current)

    if arg == "-":
        return slower(current)

    try:
        value = float(arg)
    except ValueError:
        return None

    is_relative = arg.startswith(("+", "-"))
    return adjust_speed(current, value) if is_relative else clamp_speed(value)
