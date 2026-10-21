"""Self-test of the non-GUI logic: python test_core.py"""
import os
import pickle
import tempfile

import config
from analysis import (PREDICTORS, DigitalTwin, SavedModelPredictor, ThermalPredictor,
                      prediction_error)
from cooling import CoolingFluid, CoolingOptimizer, ThermalAnalysis, case_from_row
import charts
from database import Database
from exceptions import (ConfigError, DatabaseOperationError, InsufficientDataError, InvalidDataError,
                        InvalidIdentifierError, InvalidSensorValueError, ModelLoadError,
                        PredictionError, RecordNotFoundError)
from models import BatteryCell, Sensor, SENSOR_CLASSES, create_sensor
from recommender import most_severe, recommend
from simulator import DATASETS, ingest, load_demo_cfd
from validators import format_status, validate_battery_id


def expect(exc, fn, *a):
    try:
        fn(*a)
    except exc as e:
        print(f"  OK  {exc.__name__}: {e}")
    else:
        raise AssertionError(f"{exc.__name__} not raised")


class DummyModel:                      # stand-in for a trained model
    def predict(self, rows):
        return [42.0]


print("Validation")
assert validate_battery_id(" bat 12 ") == "BAT-0012"
assert format_status(" warning ") == "WARNING"
expect(InvalidIdentifierError, validate_battery_id, "XYZ")
expect(InvalidIdentifierError, format_status, "broken")
expect(InvalidSensorValueError, create_sensor, "temperature", -999)
expect(InvalidSensorValueError, create_sensor, "temperature", "abc")
expect(InvalidSensorValueError, create_sensor, "temperature", float("nan"))
expect(InvalidSensorValueError, create_sensor, "temperature", None)
expect(InvalidSensorValueError, create_sensor, "pressure", 5)

print("Abstract Sensor + polymorphism")
expect(TypeError, Sensor, 25)
sensors = [create_sensor(t, v) for t, v in (("temperature", 47), ("voltage", 3.8), ("current", -5),
                                              ("coolant_temperature", 36), ("coolant_flow", 0.5))]
assert {type(s) for s in sensors} == set(SENSOR_CLASSES.values())
for s in sensors:
    print(" ", s.format_message())

print("Models")
cell = BatteryCell("bat-1", cell_type="Li-ion")
for t in (30, 32, 35, 41, 47):
    cell.add_sensor(create_sensor("temperature", t))
cell.add_sensor(create_sensor("coolant_flow", 0.8))
cell.add_sensor(create_sensor("voltage", 3.8)); cell.add_sensor(create_sensor("current", 10))
print(" ", cell.process_readings())
assert cell.evaluate_status() == "WARNING"
assert abs(cell.temperature_trend() - 6.0) < 1e-9 and abs(cell.power_w() - 38.0) < 1e-9

print("Configurable thresholds")
config.set_thresholds(50, 60, 0.5)
assert cell.evaluate_status() == "NORMAL"
expect(ConfigError, config.set_thresholds, 60, 50, 1)
expect(ConfigError, config.set_thresholds, "x", 50, 1)
config.reset_thresholds()
assert cell.evaluate_status() == "WARNING"

print("Predictors / digital twin")
expect(TypeError, ThermalPredictor)
temps = cell.values("temperature")
for name, p in PREDICTORS.items():
    print(f"  {name}: {p.predict(temps, 0.8):.2f}  ({p.describe()})")
expect(InsufficientDataError, PREDICTORS["Linear Trend"].predict, [30])
assert prediction_error(48, 50) == (2, 4.0)
twin = DigitalTwin("BAT-0001", PREDICTORS["Linear Trend"])
twin.sync(cell)
rec = twin.compare(twin.predict_next(), 50.0)
assert twin.history == [rec] and rec["abs_error"] >= 0
expect(InsufficientDataError, DigitalTwin("BAT-0002", PREDICTORS["Linear Trend"]).sync, BatteryCell("BAT-0002"))

print("Saved model loading")
expect(ModelLoadError, SavedModelPredictor, "no_such_model.pkl")
with tempfile.TemporaryDirectory() as d:
    bad = os.path.join(d, "bad.pkl"); open(bad, "wb").write(b"not a pickle")
    expect(ModelLoadError, SavedModelPredictor, bad)
    good = os.path.join(d, "good.pkl"); pickle.dump(DummyModel(), open(good, "wb"))
    assert SavedModelPredictor(good).predict([30, 31], 2.0) == 42.0
    nomethod = os.path.join(d, "nm.pkl"); pickle.dump({"a": 1}, open(nomethod, "wb"))
    expect(ModelLoadError, SavedModelPredictor, nomethod)

print("Database CRUD")
db = Database(":memory:")
rid = db.create("sensor_readings", {"battery_id": "BAT-0001", "sensor_type": "temperature",
                                    "value": 30.5, "unit": "C", "timestamp": "now"})
assert db.read("sensor_readings", rid)["value"] == 30.5
db.update("sensor_readings", rid, {"value": 31.0})
assert db.read("sensor_readings", rid)["value"] == 31.0
db.delete("sensor_readings", rid)
expect(RecordNotFoundError, db.read, "sensor_readings", rid)
expect(RecordNotFoundError, db.delete, "sensor_readings", 999)
expect(DatabaseOperationError, db.create, "sensor_readings", {"bad_col": 1})
expect(DatabaseOperationError, db.read_all, "no_such_table")
expect(DatabaseOperationError, db.read_all, "cfd_results", "BAT-0001")
db.ensure_battery("BAT-0001"); db.ensure_battery("BAT-0001")
assert len(db.read_all("battery_cells")) == 1
for t in ("battery_cells", "cfd_results", "predictions", "maintenance_records"):
    col = {"cfd_results": "case_name"}.get(t, "battery_id")
    extra = {"cell_id": "C09"} if t == "battery_cells" else {}
    i = db.create(t, {col: "A", **extra})
    db.update(t, i, {col: "B"})
    assert db.read(t, i)[col] == "B"
    db.delete(t, i)

print("Cooling comparison")
expect(TypeError, CoolingFluid, 1, 2, 3, 4, 5, 6)
assert load_demo_cfd(db) == 7 and load_demo_cfd(db) == 0
cases = [case_from_row(r) for r in db.read_all("cfd_results")]
opt = CoolingOptimizer(cases)
ranked = opt.ranked()
assert ranked[0].case_name == "Water Re500" and ranked[-1].case_name == "Water Re200"
assert len(opt.feasible()) == 6 and opt.summary()["best"].case_name == "Water Re500"
for row in opt.table():
    print(" ", row)
expect(InvalidDataError, case_from_row, {"reynolds_number": 0, "inlet_temperature": 25,
       "nanoparticle_concentration": 0, "pressure_drop": 10, "heat_transfer_coefficient": 5,
       "max_temperature": 30})
assert ThermalAnalysis.delta_t(30, 36) == 6 and ThermalAnalysis.uniformity({"a": 30}) is None
assert ThermalAnalysis.uniformity({"a": 30, "b": 33}) == (3, True)
assert ThermalAnalysis.uniformity({"a": 30, "b": 36})[1] is False

print("Recommender")
recs = recommend(cell, predicted=52.0)
for r in recs:
    print(f"  [{r.basis}] ({r.alert_type}) {r.text}")
assert {r.basis for r in recs} == {"Measured", "Estimated"}
assert most_severe(recs).severity >= 2
assert recommend(BatteryCell("BAT-0009"))[0].alert_type == "NO_DATA"

print("Simulated datasets")
expected = {"Normal operation": "NORMAL", "Elevated temperature": "CRITICAL",
            "Low coolant flow": "WARNING", "Missing data": "NORMAL", "Sensor faults": "NORMAL"}
for i, name in enumerate(DATASETS, start=1):
    bid = f"BAT-{i + 10:04d}"
    saved, rejected = ingest(db, bid, name)
    c = BatteryCell(bid)
    for row in db.read_all("sensor_readings", battery_id=bid):
        c.add_sensor(create_sensor(row["sensor_type"], row["value"], row["timestamp"]))
    print(f"  {name}: saved={saved}, rejected={len(rejected)}, status={c.evaluate_status()}")
    assert c.evaluate_status() == expected[name]
    assert (len(rejected) > 0) == (name in ("Missing data", "Sensor faults"))
assert any("missing" in m for m in ingest(db, "BAT-0020", "Missing data")[1])

print("Chart drawing (geometry stays inside the canvas)")
t = config.THRESHOLDS
def inside(scene, w, h, name):
    for it in scene:
        xs, ys = it["coords"][0::2], it["coords"][1::2]
        if it["kind"] == "arc":          # coords are the FULL circle's box; only the top half is drawn
            ys = ys[:1] + [(ys[0] + ys[1]) / 2]
        assert all(-1 <= x <= w + 1 for x in xs) and all(-1 <= y <= h + 1 for y in ys), (name, it)
    print(f"  OK  {name}: {len(scene)} primitives")
for v in (None, -5, 0, 23.5, 47, 80, 120):
    inside(charts.gauge(300, 210, v, t), 300, 210, f"gauge({v})")
inside(charts.temperature_chart(640, 260, [], t), 640, 260, "trend chart, no data")
inside(charts.temperature_chart(640, 260, [30], t), 640, 260, "trend chart, 1 reading")
inside(charts.temperature_chart(640, 260, list(range(20, 80)), t, predicted=95.0), 640, 260, "trend chart, 60 readings + estimate")
inside(charts.bar_chart(900, 190, [], "empty"), 900, 190, "bar chart, empty")
inside(charts.bar_chart(900, 190, [("a", 3.0, "#000"), ("b", 1.0, "#000")], "bars"), 900, 190, "bar chart")
inside(charts.header(1080, 58), 1080, 58, "header banner")
assert charts.temp_color(60, t) == charts.COL["red"] and charts.temp_color(30, t) == charts.COL["green"]

print("\nALL TESTS PASSED")
