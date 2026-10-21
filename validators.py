"""Validation and formatting of identifiers, status strings and readings."""
import math
import re

from exceptions import InvalidIdentifierError, InvalidSensorValueError

# sensor_type: (min, max, unit)
SENSOR_LIMITS = {
    "temperature": (-40.0, 150.0, "C"),
    "voltage": (0.0, 5.0, "V"),
    "current": (-150.0, 150.0, "A"),
    "coolant_temperature": (-40.0, 100.0, "C"),
    "coolant_flow": (0.0, 10.0, "L/min"),
}

VALID_STATUSES = ("NORMAL", "WARNING", "CRITICAL", "FAULT")


def validate_battery_id(raw):
    """Clean and validate a battery ID. 'bat 12' / ' bat_0012 ' -> 'BAT-0012'."""
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidIdentifierError("Battery ID cannot be empty.")
    text = re.sub(r"[\s_]+", "-", raw.strip().upper())
    match = re.fullmatch(r"BAT-?(\d{1,4})", text)
    if not match:
        raise InvalidIdentifierError(
            f"Invalid battery ID '{raw}'. Expected format: BAT-0001.")
    return f"BAT-{int(match.group(1)):04d}"


def format_status(raw):
    """Clean and validate a status string -> upper-case member of VALID_STATUSES."""
    if not isinstance(raw, str):
        raise InvalidIdentifierError("Status must be text.")
    status = raw.strip().upper()
    if status not in VALID_STATUSES:
        raise InvalidIdentifierError(
            f"Invalid status '{raw}'. Allowed: {', '.join(VALID_STATUSES)}.")
    return status


def normalize_sensor_type(sensor_type):
    stype = str(sensor_type).strip().lower().replace(" ", "_")
    if stype not in SENSOR_LIMITS:
        raise InvalidSensorValueError(
            f"Unknown sensor type '{sensor_type}'. Allowed: {', '.join(SENSOR_LIMITS)}.")
    return stype


def validate_sensor_reading(sensor_type, value):
    """Return (sensor_type, float_value, unit) or raise InvalidSensorValueError."""
    stype = normalize_sensor_type(sensor_type)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise InvalidSensorValueError(f"{stype} reading is missing.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InvalidSensorValueError(f"{stype} reading '{value}' is not a number.")
    if math.isnan(number) or math.isinf(number):
        raise InvalidSensorValueError(f"{stype} reading is NaN/infinite (possible sensor fault).")
    low, high, unit = SENSOR_LIMITS[stype]
    if not low <= number <= high:
        raise InvalidSensorValueError(
            f"{stype} reading {number} is outside the valid range {low} to {high} {unit}.")
    return stype, number, unit
