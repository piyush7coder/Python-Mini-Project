# KJS-CES-02 - AI-Enabled Micro-channel Battery Thermal Management System

Python 3 + Tkinter + SQLite. No extra packages needed.

    python main.py        # start the dashboard
    python test_core.py   # run the self-test (no GUI needed)

All data is simulated/demonstration data. Thresholds, rules and prediction models are
demonstration values - not engineering-approved - and the app never controls real equipment.

## Files
| File | Purpose |
|---|---|
| models.py | `BatteryCell`; abstract `Sensor` + Temperature/Voltage/Current/CoolantTemperature/CoolantFlow sensors (polymorphism) |
| validators.py | Battery ID / status / sensor reading validation and formatting |
| exceptions.py | Custom exceptions (invalid value, database failure, missing record, model load ...) |
| analysis.py | Abstract `ThermalPredictor` + 3 demo predictors + `SavedModelPredictor` (optional `thermal_model.pkl`), `DigitalTwin`, prediction error |
| cooling.py | Abstract `CoolingFluid` (Water / Al2O3 nanofluid), `ThermalAnalysis` (delta-T), `CoolingOptimizer` (filter/map/sorted/lambda) |
| recommender.py | Rule-based recommendations tagged Measured / Estimated |
| database.py | SQLite schema + CRUD, parameterized queries, cursors closed |
| simulator.py | Test datasets: normal, elevated temp, low flow, missing data, sensor faults + demo CFD cases |
| config.py | Configurable demonstration thresholds |
| charts.py | Gauge, temperature trend chart, bar chart and header drawn on Tkinter canvases |
| gui.py / main.py | Tkinter dashboard (Dashboard, readings, prediction, cooling, history, maintenance tabs) |
