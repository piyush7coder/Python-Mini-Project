"""Configurable thresholds.

IMPORTANT: these are DEMONSTRATION values for a classroom project. The 15-45 C
range and delta-T < 5 C come from the project brief; they are not universal
guarantees and are not engineering-approved for any real battery.
"""
from exceptions import ConfigError

DEFAULTS = {
    "temp_min": 15.0,        # C, lower end of project target range
    "temp_warning": 45.0,    # C, upper end of project target range
    "temp_critical": 55.0,   # C, demonstration critical level
    "low_flow": 1.0,         # L/min, demonstration low-flow level
    "delta_t_target": 5.0,   # C, temperature-uniformity target
    "rapid_rise": 2.0,       # C per reading, demonstration rapid-rise level
}
THRESHOLDS = dict(DEFAULTS)


def set_thresholds(warning, critical, low_flow):
    """Update the user-configurable thresholds after validating them."""
    try:
        warning, critical, low_flow = float(warning), float(critical), float(low_flow)
    except (TypeError, ValueError):
        raise ConfigError("Thresholds must be numbers.")
    if not warning < critical:
        raise ConfigError("Warning threshold must be lower than the critical threshold.")
    if low_flow < 0:
        raise ConfigError("Low-flow threshold cannot be negative.")
    THRESHOLDS.update(temp_warning=warning, temp_critical=critical, low_flow=low_flow)


def reset_thresholds():
    THRESHOLDS.update(DEFAULTS)
