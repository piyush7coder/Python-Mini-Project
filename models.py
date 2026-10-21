"""Battery cell and ABSTRACT sensor classes (Scenarios 1, 2, 4 of the brief).

Sensor is an abstract base class; each concrete sensor overrides
status_message(), so calling it on a mixed list demonstrates polymorphism.
"""
from abc import ABC, abstractmethod
from datetime import datetime

import config
from exceptions import InvalidSensorValueError
from validators import (validate_battery_id, format_status, validate_sensor_reading,
                        normalize_sensor_type)


class Sensor(ABC):
    """Abstract sensor: validated value + timestamp + a status message."""
    sensor_type = None   # set by subclasses
    label = None

    def __init__(self, value, timestamp=None):
        _, self.value, self.unit = validate_sensor_reading(self.sensor_type, value)
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def read_value(self):
        return self.value

    @abstractmethod
    def status_message(self):
        """Short human-readable interpretation of the current value."""

    def format_message(self):
        return (f"[{self.timestamp}] {self.label.upper():<19} "
                f"{self.value:>8.2f} {self.unit:<6} - {self.status_message()}")

    def __str__(self):
        return self.format_message()


class TemperatureSensor(Sensor):
    sensor_type, label = "temperature", "Battery temperature"

    def status_message(self):
        t = config.THRESHOLDS
        if self.value >= t["temp_critical"]:
            return "CRITICAL temperature"
        if self.value >= t["temp_warning"]:
            return "High temperature"
        if self.value < t["temp_min"]:
            return "Below recommended range"
        return "Within range"


class VoltageSensor(Sensor):
    sensor_type, label = "voltage", "Cell voltage"

    def status_message(self):
        if self.value < 3.0:
            return "Low voltage"
        if self.value > 4.25:
            return "High voltage"
        return "Normal"


class CurrentSensor(Sensor):
    sensor_type, label = "current", "Cell current"

    def status_message(self):
        if self.value < 0:
            return "Charging"
        return "Discharging" if self.value > 0 else "Idle"


class CoolantTemperatureSensor(Sensor):
    sensor_type, label = "coolant_temperature", "Coolant temperature"

    def status_message(self):
        return "Coolant warm - reduced margin" if self.value >= 35 else "Coolant OK"


class CoolantFlowSensor(Sensor):
    sensor_type, label = "coolant_flow", "Coolant flow"

    def status_message(self):
        return "LOW flow" if self.value < config.THRESHOLDS["low_flow"] else "Flow OK"


SENSOR_CLASSES = {cls.sensor_type: cls for cls in (
    TemperatureSensor, VoltageSensor, CurrentSensor, CoolantTemperatureSensor, CoolantFlowSensor)}


def create_sensor(sensor_type, value, timestamp=None):
    """Factory: build the right Sensor subclass (validates type and value)."""
    return SENSOR_CLASSES[normalize_sensor_type(sensor_type)](value, timestamp)


class BatteryCell:
    """A battery cell that owns a LIST of Sensor objects."""

    def __init__(self, battery_id, cell_id="C01", cell_type="Li-ion", capacity_ah=0.0, status="NORMAL"):
        self.battery_id = validate_battery_id(battery_id)
        self.cell_id = str(cell_id).strip() or "C01"
        self.cell_type = str(cell_type).strip() or "Li-ion"
        self.capacity_ah = float(capacity_ah)
        self.status = format_status(status)
        self.sensors = []          # list of Sensor objects

    def add_sensor(self, sensor):
        self.sensors.append(sensor)

    def values(self, sensor_type):
        return [s.value for s in self.sensors if s.sensor_type == sensor_type]

    def latest(self, sensor_type):
        vals = self.values(sensor_type)
        return vals[-1] if vals else None

    def average(self, sensor_type):
        vals = self.values(sensor_type)
        return sum(vals) / len(vals) if vals else None

    def maximum(self, sensor_type):
        vals = self.values(sensor_type)
        return max(vals) if vals else None

    def temperature_trend(self, n=3):
        """Average temperature change per reading over the last n readings (None if < 2)."""
        temps = self.values("temperature")[-n:]
        if len(temps) < 2:
            return None
        return (temps[-1] - temps[0]) / (len(temps) - 1)

    def power_w(self):
        """Latest voltage x |current| in watts (None if either is missing)."""
        v, i = self.latest("voltage"), self.latest("current")
        return None if v is None or i is None else v * abs(i)

    def process_readings(self):
        """Summarise every sensor type held in the list."""
        summary = {}
        for stype in sorted({s.sensor_type for s in self.sensors}):
            vals = self.values(stype)
            summary[stype] = {"count": len(vals), "min": min(vals), "max": max(vals),
                              "avg": round(sum(vals) / len(vals), 2), "latest": vals[-1]}
        return summary

    def evaluate_status(self):
        """Rule-based status from latest temperature/flow (configurable demo thresholds)."""
        t = config.THRESHOLDS
        temp, flow = self.latest("temperature"), self.latest("coolant_flow")
        if temp is None:
            return self.status
        low_flow = flow is not None and flow < t["low_flow"]
        if temp >= t["temp_critical"]:
            self.status = "CRITICAL"
        elif temp >= t["temp_warning"] or temp < t["temp_min"] or (low_flow and temp >= 40):
            self.status = "WARNING"
        else:
            self.status = "NORMAL"
        return self.status

    def __str__(self):
        return f"{self.battery_id}/{self.cell_id} ({self.cell_type}) [{self.status}] - {len(self.sensors)} readings"
