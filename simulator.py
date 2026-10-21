"""Simulated test datasets: normal, elevated temperature, low coolant flow, missing
data and sensor faults, plus DEMO CFD cases. ALL values here are synthetic teaching
data, not real measurements or real CFD results."""
from datetime import datetime

from exceptions import InvalidSensorValueError
from models import create_sensor

NAN = float("nan")


def _steps(temps, flows, current=10.0, volts=3.8, coolant=25.0):
    """Build (sensor_type, value) rows; scalars are repeated, lists are used as given."""
    n = len(temps)
    rep = lambda x: x if isinstance(x, list) else [x] * n
    flows, volts, current, coolant = rep(flows), rep(volts), rep(current), rep(coolant)
    rows = []
    for i in range(n):
        rows += [("temperature", temps[i]), ("voltage", volts[i]), ("current", current[i]),
                 ("coolant_temperature", coolant[i]), ("coolant_flow", flows[i])]
    return rows


DATASETS = {
    "Normal operation": _steps([28, 29, 30, 30, 31, 31, 32, 32], 3.0),
    "Elevated temperature": _steps([35, 38, 42, 46, 49, 52, 55, 58], 2.5, current=40.0,
                                   coolant=[28, 29, 30, 31, 32, 33, 34, 35]),
    "Low coolant flow": _steps([32, 35, 39, 43, 47, 50], [1.5, 1.2, 0.9, 0.7, 0.6, 0.5], current=20.0),
    "Missing data": _steps([30, None, 32, "", 33, 34], [3.0, 3.0, None, 3.0, "", 3.0]),
    "Sensor faults": _steps([30, 31, -999, "ERR", 33, NAN, 34, 200],
                            [3.0, -1, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
                            volts=[3.8, 9.9, 3.8, 3.8, 3.8, 3.8, 3.8, 3.8],
                            current=[10, 10, "abc", 10, 10, 10, 10, 10]),
}

# (case_name, reynolds, inlet C, concentration % vol, pressure drop Pa, h W/m2K, max temp C)
DEMO_CFD_CASES = [
    ("Water Re200", 200, 25, 0, 50, 900, 47.5),
    ("Water Re500", 500, 25, 0, 120, 1500, 41.5),
    ("Water Re1000", 1000, 25, 0, 260, 2100, 38.2),
    ("Water Re1500", 1500, 25, 0, 480, 2600, 36.1),
    ("Al2O3 1% Re1000", 1000, 25, 1, 280, 2350, 37.0),
    ("Al2O3 2% Re1000", 1000, 25, 2, 310, 2550, 36.2),
    ("Al2O3 3% Re1000", 1000, 25, 3, 360, 2650, 35.9),
]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ingest(db, battery_id, dataset_name):
    """Validate and store a dataset. Returns (saved_count, rejected_messages)."""
    db.ensure_battery(battery_id)
    saved, rejected = 0, []
    for stype, raw in DATASETS[dataset_name]:
        try:
            sensor = create_sensor(stype, raw)
        except InvalidSensorValueError as exc:
            rejected.append(str(exc))
            continue
        db.create("sensor_readings", {"battery_id": battery_id, "sensor_type": sensor.sensor_type,
                                      "value": sensor.value, "unit": sensor.unit,
                                      "timestamp": sensor.timestamp})
        saved += 1
    return saved, rejected


def load_demo_cfd(db):
    """Insert the synthetic CFD cases once. Returns number of rows added."""
    if any(str(r["notes"]).startswith("DEMO") for r in db.read_all("cfd_results")):
        return 0
    for name, re_no, inlet, conc, dp, h, tmax in DEMO_CFD_CASES:
        db.create("cfd_results", {
            "case_name": name, "fluid": "Water" if conc == 0 else "Al2O3/water",
            "reynolds_number": re_no, "inlet_temperature": inlet,
            "nanoparticle_concentration": conc, "pressure_drop": dp,
            "heat_transfer_coefficient": h, "max_temperature": tmax,
            "notes": "DEMO: synthetic teaching data, not real CFD", "created_at": _now()})
    return len(DEMO_CFD_CASES)
