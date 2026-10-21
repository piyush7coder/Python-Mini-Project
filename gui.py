"""Tkinter dashboard: data entry, status indicator, reading table, alerts, prediction vs
observed, cooling comparison, history + recommendations, maintenance log."""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import config
import charts
from analysis import PREDICTORS, TWIN_DISCLAIMER, DigitalTwin, SavedModelPredictor
from cooling import CoolingOptimizer, ThermalAnalysis, case_from_row
from database import Database
from exceptions import (BatteryTMSError, ConfigError, DatabaseOperationError, InsufficientDataError,
                        InvalidDataError, InvalidIdentifierError, InvalidSensorValueError,
                        ModelLoadError, PredictionError, RecordNotFoundError)
from models import BatteryCell, create_sensor
from recommender import DISCLAIMER, most_severe, recommend
from simulator import DATASETS, ingest, load_demo_cfd
from validators import SENSOR_LIMITS, validate_battery_id, validate_sensor_reading

MODEL_FILE = "thermal_model.pkl"   # optional trained model (pickle); demo models used if absent
BG, NAVY, TEAL, TEAL_D, INK, LINE = "#f3f6fb", "#101a2c", "#39d6bd", "#087f8c", "#172337", "#dce5f0"
TAG_COLORS = {"even": "#ffffff", "odd": "#f3f7fc", "crit": "#fde2e0", "warn": "#fff1d6", "good": "#e3f6ea",
              "est": "#efe8fb", "meas": "#e8f1fb", "muted": "#eceff3"}
GAUGE_SIZE, CHART_SIZE, BAR_SIZE = (300, 210), (640, 260), (900, 190)
STATUS_COLORS = {"NORMAL": "#2ecc71", "WARNING": "#f1c40f", "CRITICAL": "#e74c3c", "FAULT": "#7f8c8d"}
ERROR_TITLES = {InvalidIdentifierError: "Invalid ID", InvalidSensorValueError: "Invalid Sensor Value",
                DatabaseOperationError: "Database Error", RecordNotFoundError: "Record Not Found",
                InsufficientDataError: "Not Enough Data", ConfigError: "Invalid Threshold",
                ModelLoadError: "Model Error", PredictionError: "Prediction Error",
                InvalidDataError: "Invalid Data"}


def _make_table(parent, columns, widths, height):
    table = ttk.Treeview(parent, columns=columns, show="headings", height=height)
    for col, width in zip(columns, widths):
        table.heading(col, text=col.replace("_", " ").title())
        table.column(col, width=width, anchor="center")
    for tag, colour in TAG_COLORS.items():
        table.tag_configure(tag, background=colour)
    return table


class App(tk.Tk):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.title("Battery Thermal Management System")
        self.geometry("1380x960")
        self.minsize(1120, 780)
        self.configure(bg=BG)
        self._apply_theme()
        self.kpi = {}
        self.last_prediction = None      # (battery_id, predictor, predicted, twin)
        self._last_recs = []
        self.predictors = dict(PREDICTORS)
        self._load_saved_model()

        self.cell_var = tk.StringVar(value="BAT-0001")
        self.type_var = tk.StringVar(value="temperature")
        self.value_var = tk.StringVar()
        self.dataset_var = tk.StringVar(value=list(DATASETS)[0])
        self.model_var = tk.StringVar(value=list(self.predictors)[0])
        self.observed_var = tk.StringVar()
        self.warn_var = tk.StringVar(value=str(config.THRESHOLDS["temp_warning"]))
        self.crit_var = tk.StringVar(value=str(config.THRESHOLDS["temp_critical"]))
        self.flow_var = tk.StringVar(value=str(config.THRESHOLDS["low_flow"]))

        self._build_header()
        self._build_entry_frame()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._build_dashboard_tab(notebook)
        self._build_readings_tab(notebook)
        self._build_prediction_tab(notebook)
        self._build_cooling_tab(notebook)
        self._build_history_tab(notebook)
        self._build_maintenance_tab(notebook)
        self.refresh_all()

    # ---------------- layout ----------------
    # ---------------- look and feel ----------------
    def _apply_theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")     # theme that honours custom colours on every platform
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=INK, font=("Helvetica", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("TLabelframe", background=BG, bordercolor=LINE)
        style.configure("TLabelframe.Label", background=BG, foreground=NAVY, font=("Helvetica", 10, "bold"))
        style.configure("TButton", background=TEAL_D, foreground="white", padding=(13, 8),
                        borderwidth=0, font=("Helvetica", 10, "bold"), relief="flat")
        style.map("TButton", background=[("active", "#12a99a"), ("pressed", NAVY)],
                  foreground=[("disabled", "#9aa8b9")])
        style.configure("Treeview", background="white", fieldbackground="white", rowheight=31, bordercolor=LINE,
                        font=("Helvetica", 10), padding=3)
        style.configure("Treeview.Heading", background=NAVY, foreground="white",
                        font=("Helvetica", 10, "bold"), padding=(8, 10))
        style.map("Treeview.Heading", background=[("active", NAVY)])
        style.map("Treeview", background=[("selected", "#bfe3dd")], foreground=[("selected", INK)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 11), font=("Helvetica", 10, "bold"),
                        background="#e4ebf5", foreground="#52647d")
        style.map("TNotebook.Tab", background=[("selected", NAVY)], foreground=[("selected", "#ffffff")])
        style.configure("TEntry", fieldbackground="white", padding=4)
        style.configure("TCombobox", fieldbackground="white", padding=4)

    def _build_header(self):
        canvas = tk.Canvas(self, height=82, bg=NAVY, highlightthickness=0)
        canvas.pack(fill="x")
        charts.draw_items(canvas, charts.header())

    def _make_card(self, parent, title):
        frame = tk.Frame(parent, bg="white", highlightthickness=1, highlightbackground="#d7e1ed", bd=0)
        frame.pack(side="left", fill="x", expand=True, padx=4)
        strip = tk.Frame(frame, width=7, bg=TEAL)
        strip.pack(side="left", fill="y")
        inner = tk.Frame(frame, bg="white")
        inner.pack(side="left", fill="x", expand=True, padx=13, pady=12)
        tk.Label(inner, text=title, bg="white", fg="#6b7a90", font=("Helvetica", 9, "bold")).pack(anchor="w")
        value = tk.Label(inner, text="-", bg="white", fg=NAVY, font=("Helvetica", 23, "bold"))
        value.pack(anchor="w")
        return {"strip": strip, "value": value}

    def _build_dashboard_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Dashboard")
        cards = tk.Frame(tab, bg=BG)
        cards.pack(fill="x", padx=12, pady=(14, 18))
        for key, title in (("temp", "Battery temperature"), ("flow", "Coolant flow"), ("volt", "Cell voltage"),
                           ("power", "Power (V x |I|)"), ("status", "Status")):
            self.kpi[key] = self._make_card(cards, title)
        row = tk.Frame(tab, bg=BG)
        row.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.gauge_canvas = tk.Canvas(row, width=GAUGE_SIZE[0], height=GAUGE_SIZE[1], bg="white",
                                      highlightthickness=1, highlightbackground=LINE)
        self.gauge_canvas.pack(side="left", padx=(4, 8))
        self.chart_canvas = tk.Canvas(row, width=CHART_SIZE[0], height=CHART_SIZE[1], bg="white",
                                      highlightthickness=1, highlightbackground=LINE)
        self.chart_canvas.pack(side="left")
        ttk.Label(tab, text="LIVE MONITORING  /  Solid line = measured data  ·  Dashed violet marker = model estimate (not a measurement)",
                  foreground="#52647d").pack(anchor="w", padx=16, pady=(6, 12))

    def _build_entry_frame(self):
        frame = ttk.LabelFrame(self, text="Data Entry")
        frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(frame, text="Battery ID:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.cell_var, width=12).grid(row=0, column=1)
        ttk.Label(frame, text="Sensor:").grid(row=0, column=2, padx=5)
        ttk.Combobox(frame, textvariable=self.type_var, values=list(SENSOR_LIMITS),
                     state="readonly", width=19).grid(row=0, column=3)
        ttk.Label(frame, text="Value:").grid(row=0, column=4, padx=5)
        ttk.Entry(frame, textvariable=self.value_var, width=10).grid(row=0, column=5)
        ttk.Button(frame, text="Add Reading", command=self.add_reading).grid(row=0, column=6, padx=10)
        self.indicator = tk.Canvas(frame, width=24, height=24, highlightthickness=0)
        self.light = self.indicator.create_oval(3, 3, 21, 21, fill="#bdc3c7")
        self.indicator.grid(row=0, column=7, padx=(20, 2))
        self.status_label = ttk.Label(frame, text="STATUS: -", width=20)
        self.status_label.grid(row=0, column=8)

        ttk.Label(frame, text="Test dataset:").grid(row=1, column=0, padx=5, pady=5)
        ttk.Combobox(frame, textvariable=self.dataset_var, values=list(DATASETS),
                     state="readonly", width=19).grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Button(frame, text="Load Dataset", command=self.load_dataset).grid(row=1, column=4, columnspan=2)
        ttk.Button(frame, text="Refresh", command=self.refresh_all).grid(row=1, column=6)
        ttk.Button(frame, text="View Summary", command=self.view_summary).grid(row=1, column=7, columnspan=2)

        th = ttk.Frame(frame)
        th.grid(row=2, column=0, columnspan=9, sticky="w", padx=5, pady=5)
        ttk.Label(th, text="Demo thresholds (not engineering-approved):").pack(side="left")
        for text, var in (("Warn >=", self.warn_var), ("Critical >=", self.crit_var),
                          ("Low flow <", self.flow_var)):
            ttk.Label(th, text=text).pack(side="left", padx=(8, 2))
            ttk.Entry(th, textvariable=var, width=6).pack(side="left")
        ttk.Button(th, text="Apply", command=self.apply_thresholds).pack(side="left", padx=8)

    def _build_readings_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Measured Readings")
        cols = ("id", "battery_id", "sensor_type", "value", "unit", "timestamp")
        self.reading_table = _make_table(tab, cols, (50, 90, 140, 80, 70, 160), 15)
        self.reading_table.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Button(tab, text="Delete Selected", command=self.delete_reading).pack(pady=5)

    def _build_prediction_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Prediction vs Observed")
        top = ttk.Frame(tab); top.pack(fill="x", padx=5, pady=8)
        ttk.Label(top, text="Model:").pack(side="left")
        ttk.Combobox(top, textvariable=self.model_var, values=list(self.predictors),
                     state="readonly", width=16).pack(side="left", padx=5)
        ttk.Button(top, text="Predict Next Temp", command=self.run_prediction).pack(side="left", padx=5)
        self.pred_label = ttk.Label(top, text="Estimated: -")
        self.pred_label.pack(side="left", padx=10)
        ttk.Label(tab, text=TWIN_DISCLAIMER, foreground="#b9770e").pack(anchor="w", padx=8)

        row = ttk.Frame(tab); row.pack(fill="x", padx=5, pady=4)
        ttk.Label(row, text="Observed temp (C):").pack(side="left")
        ttk.Entry(row, textvariable=self.observed_var, width=10).pack(side="left", padx=5)
        ttk.Button(row, text="Compare & Save", command=self.compare_and_save).pack(side="left", padx=5)

        cols = ("id", "battery_id", "model_name", "predicted_temperature", "observed_temperature",
                "abs_error", "pct_error")
        self.pred_table = _make_table(tab, cols, (40, 80, 110, 140, 140, 90, 90), 12)
        self.pred_table.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_cooling_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Cooling Comparison")
        ttk.Label(tab, text="DEMO data: synthetic values for teaching only - not real CFD or "
                            "experimental results. Ranking index = h / pressure drop (demo criterion).",
                  foreground="#b9770e").pack(anchor="w", padx=8, pady=4)
        bar = ttk.Frame(tab); bar.pack(fill="x", padx=5, pady=4)
        ttk.Button(bar, text="Load Demo CFD Cases", command=self.load_demo_cases).pack(side="left")
        ttk.Button(bar, text="Refresh Ranking", command=self.refresh_cooling).pack(side="left", padx=8)
        self.best_label = ttk.Label(bar, text="")
        self.best_label.pack(side="left", padx=10)
        cols = ("rank", "fluid", "conc_pct", "reynolds", "max_temp_c", "pressure_drop_pa",
                "h_w_m2k", "index", "benefit_vs_water_c", "within_limit")
        self.cool_table = _make_table(tab, cols, (45, 95, 70, 75, 85, 110, 80, 70, 130, 90), 8)
        self.cool_table.pack(fill="x", padx=5, pady=5)
        self.cool_canvas = tk.Canvas(tab, width=BAR_SIZE[0], height=BAR_SIZE[1], bg="white",
                                     highlightthickness=1, highlightbackground=LINE)
        self.cool_canvas.pack(padx=5, pady=5)

    def _build_history_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="History & Recommendations")
        bar = ttk.Frame(tab); bar.pack(fill="x", padx=5, pady=6)
        ttk.Button(bar, text="Show for Battery ID", command=self.refresh_history).pack(side="left")
        ttk.Button(bar, text="Save as Maintenance Record", command=self.save_maintenance).pack(side="left", padx=8)
        self.summary_label = ttk.Label(bar, text="")
        self.summary_label.pack(side="left", padx=10)

        rec_frame = ttk.LabelFrame(tab, text="Cooling Recommendations")
        rec_frame.pack(fill="x", padx=5, pady=4)
        self.rec_table = _make_table(rec_frame, ("basis", "alert_type", "recommendation"), (90, 130, 700), 6)
        self.rec_table.pack(fill="x", padx=4, pady=4)
        ttk.Label(rec_frame, text=DISCLAIMER, foreground="#b9770e").pack(anchor="w", padx=6)
        self.uniform_label = ttk.Label(rec_frame, text="")
        self.uniform_label.pack(anchor="w", padx=6, pady=(0, 4))

        hist = ttk.LabelFrame(tab, text="Historical Readings (measured)")
        hist.pack(fill="both", expand=True, padx=5, pady=4)
        self.hist_table = _make_table(hist, ("id", "sensor_type", "value", "unit", "timestamp"),
                                      (50, 140, 90, 70, 170), 8)
        self.hist_table.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_maintenance_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Maintenance Log")
        cols = ("id", "battery_id", "alert_type", "description", "timestamp", "status")
        self.maint_table = _make_table(tab, cols, (40, 80, 110, 430, 140, 80), 15)
        self.maint_table.pack(fill="both", expand=True, padx=5, pady=5)
        bar = ttk.Frame(tab); bar.pack(pady=5)
        ttk.Button(bar, text="Mark Resolved", command=self.mark_resolved).pack(side="left", padx=5)
        ttk.Button(bar, text="Delete Selected", command=self.delete_maintenance).pack(side="left", padx=5)

    # ---------------- helpers ----------------
    def _show_error(self, exc):
        messagebox.showerror(ERROR_TITLES.get(type(exc), "Error"), str(exc))

    def _load_saved_model(self):
        if not os.path.exists(MODEL_FILE):
            return
        try:
            predictor = SavedModelPredictor(MODEL_FILE)
            self.predictors[predictor.name] = predictor
        except ModelLoadError as exc:
            messagebox.showwarning("Model not loaded", f"{exc}\nUsing demonstration models instead.")

    def load_cell(self, battery_id):
        """Rebuild a BatteryCell (with its list of Sensor objects) from the database."""
        cell = BatteryCell(battery_id)
        for row in self.db.read_all("sensor_readings", battery_id=battery_id):
            try:
                cell.add_sensor(create_sensor(row["sensor_type"], row["value"], row["timestamp"]))
            except InvalidSensorValueError:
                continue
        return cell

    def latest_temps(self):
        """Latest measured temperature for every registered battery."""
        temps = {}
        for row in self.db.read_all("battery_cells"):
            temp = self.load_cell(row["battery_id"]).latest("temperature")
            if temp is not None:
                temps[row["battery_id"]] = temp
        return temps

    def update_status(self, battery_id, alert=True):
        cell = self.load_cell(battery_id)
        status = cell.evaluate_status()
        self.indicator.itemconfig(self.light, fill=STATUS_COLORS[status])
        self.status_label.config(text=f"STATUS: {status}")
        if alert and status in ("WARNING", "CRITICAL"):
            messagebox.showwarning(f"{status} ALERT",
                                   f"{battery_id} is {status}.\nLatest temperature: {cell.latest('temperature')} C")
        return status

    # ---------------- actions: readings ----------------
    def add_reading(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            self.cell_var.set(battery_id)
            sensor = create_sensor(self.type_var.get(), self.value_var.get())
            self.db.ensure_battery(battery_id)
            self.db.create("sensor_readings", {
                "battery_id": battery_id, "sensor_type": sensor.sensor_type, "value": sensor.value,
                "unit": sensor.unit, "timestamp": sensor.timestamp})
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self.value_var.set("")
        self.refresh_all()
        self.update_status(battery_id)

    def delete_reading(self):
        selected = self.reading_table.selection()
        if not selected:
            messagebox.showinfo("Delete", "Select a reading first.")
            return
        try:
            self.db.delete("sensor_readings", int(selected[0]))
        except BatteryTMSError as exc:
            self._show_error(exc)
        self.refresh_all()

    def load_dataset(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            self.cell_var.set(battery_id)
            name = self.dataset_var.get()
            saved, rejected = ingest(self.db, battery_id, name)
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self.refresh_all()
        status = self.update_status(battery_id, alert=False)
        msg = f"Dataset '{name}' loaded for {battery_id}.\nSaved readings: {saved}\nStatus: {status}"
        if rejected:
            self.indicator.itemconfig(self.light, fill=STATUS_COLORS["FAULT"])
            self.status_label.config(text="STATUS: SENSOR FAULT")
            msg += f"\n\nRejected {len(rejected)} faulty/missing readings:\n" + "\n".join(rejected[:6])
            messagebox.showwarning("Sensor Fault Alert", msg)
        elif status in ("WARNING", "CRITICAL"):
            messagebox.showwarning(f"{status} ALERT", msg)
        else:
            messagebox.showinfo("Dataset Loaded", msg)

    def view_summary(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            cell = self.load_cell(battery_id)
            uniformity = ThermalAnalysis.uniformity(self.latest_temps())
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        summary = cell.process_readings()
        if not summary:
            messagebox.showinfo("Summary", f"No readings stored for {battery_id}.")
            return
        lines = [f"Summary for {battery_id} (measured values)"]
        for stype, s in summary.items():
            lines.append(f"{stype}: n={s['count']}, min={s['min']}, max={s['max']}, "
                         f"avg={s['avg']}, latest={s['latest']}")
        if cell.power_w() is not None:
            lines.append(f"Power (latest V x |I|): {cell.power_w():.1f} W")
        if uniformity:
            delta, ok = uniformity
            lines.append(f"Delta-T across batteries: {delta:.1f} C "
                         f"({'within' if ok else 'exceeds'} {config.THRESHOLDS['delta_t_target']} C target)")
        messagebox.showinfo("Summary", "\n".join(lines))

    def apply_thresholds(self):
        try:
            config.set_thresholds(self.warn_var.get(), self.crit_var.get(), self.flow_var.get())
        except ConfigError as exc:
            self._show_error(exc)
            return
        messagebox.showinfo("Thresholds", "Demonstration thresholds updated.")
        self.refresh_history()

    # ---------------- actions: prediction ----------------
    def run_prediction(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            predictor = self.predictors[self.model_var.get()]
            twin = DigitalTwin(battery_id, predictor)
            twin.sync(self.load_cell(battery_id))
            predicted = twin.predict_next()
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self.last_prediction = (battery_id, predictor, predicted, twin)
        self.pred_label.config(text=f"Estimated next temp: {predicted:.2f} C  |  {predictor.describe()}")
        self.refresh_dashboard()

    def compare_and_save(self):
        if self.last_prediction is None:
            messagebox.showinfo("Compare", "Run a prediction first.")
            return
        try:
            _, observed, _ = validate_sensor_reading("temperature", self.observed_var.get())
        except InvalidSensorValueError as exc:
            self._show_error(exc)
            return
        battery_id, predictor, predicted, twin = self.last_prediction
        record = twin.compare(predicted, observed)
        try:
            self.db.create("predictions", {
                "battery_id": battery_id, "model_name": predictor.name,
                "predicted_temperature": record["predicted"], "observed_temperature": observed,
                "abs_error": record["abs_error"], "pct_error": record["pct_error"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        messagebox.showinfo("Prediction Error",
                            f"Predicted (estimate): {record['predicted']:.2f} C\n"
                            f"Observed (measured): {observed} C\n"
                            f"Absolute error: {record['abs_error']} C\nPercent error: {record['pct_error']}%")
        self.observed_var.set("")
        self.refresh_predictions()

    # ---------------- actions: cooling / history / maintenance ----------------
    def load_demo_cases(self):
        try:
            added = load_demo_cfd(self.db)
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        messagebox.showinfo("Demo CFD cases",
                            f"Added {added} synthetic demo cases." if added else "Demo cases are already loaded.")
        self.refresh_cooling()

    def save_maintenance(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            self.refresh_history()
            if not self._last_recs or self._last_recs[0].alert_type == "NO_DATA":
                messagebox.showinfo("Maintenance", "No readings to base a record on.")
                return
            top = most_severe(self._last_recs)
            text = " | ".join(f"[{r.basis}] {r.text}" for r in self._last_recs)
            self.db.create("maintenance_records", {
                "battery_id": battery_id, "alert_type": top.alert_type, "description": text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "OPEN"})
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self.refresh_maintenance()
        messagebox.showinfo("Maintenance", f"Saved record (alert type: {top.alert_type}).")

    def mark_resolved(self):
        selected = self.maint_table.selection()
        if not selected:
            messagebox.showinfo("Maintenance", "Select a record first.")
            return
        try:
            self.db.update("maintenance_records", int(selected[0]), {"status": "RESOLVED"})
        except BatteryTMSError as exc:
            self._show_error(exc)
        self.refresh_maintenance()

    def delete_maintenance(self):
        selected = self.maint_table.selection()
        if not selected:
            messagebox.showinfo("Maintenance", "Select a record first.")
            return
        try:
            self.db.delete("maintenance_records", int(selected[0]))
        except BatteryTMSError as exc:
            self._show_error(exc)
        self.refresh_maintenance()

    # ---------------- refreshers ----------------
    def refresh_all(self):
        self.refresh_readings()
        self.refresh_predictions()
        self.refresh_cooling()
        self.refresh_history()
        self.refresh_maintenance()
        self.refresh_dashboard()

    def refresh_dashboard(self):
        """Update the KPI cards, the gauge and the trend chart for the selected battery."""
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            cell = self.load_cell(battery_id)
        except BatteryTMSError:
            return                       # invalid ID typed: the Add/Load buttons will report it
        t = config.THRESHOLDS
        temp, flow, volt, power = cell.latest("temperature"), cell.latest("coolant_flow"), \
            cell.latest("voltage"), cell.power_w()
        status = cell.evaluate_status()
        show = {"temp": f"{temp:.1f} °C" if temp is not None else "-",
                "flow": f"{flow:.2f} L/min" if flow is not None else "-",
                "volt": f"{volt:.2f} V" if volt is not None else "-",
                "power": f"{power:.1f} W" if power is not None else "-", "status": status}
        for key, text in show.items():
            self.kpi[key]["value"].config(text=text)
        self.kpi["status"]["value"].config(fg=STATUS_COLORS[status])
        self.kpi["temp"]["strip"].config(bg=charts.temp_color(temp, t) if temp is not None else TEAL)
        self.kpi["flow"]["strip"].config(bg=charts.COL["amber"] if flow is not None and flow < t["low_flow"] else TEAL)
        self.kpi["status"]["strip"].config(bg=STATUS_COLORS[status])
        predicted = None
        if self.last_prediction and self.last_prediction[0] == battery_id:
            predicted = self.last_prediction[2]
        charts.draw_items(self.gauge_canvas, charts.gauge(GAUGE_SIZE[0], GAUGE_SIZE[1], temp, t))
        charts.draw_items(self.chart_canvas, charts.temperature_chart(
            CHART_SIZE[0], CHART_SIZE[1], cell.values("temperature"), t, predicted,
            f"Temperature history, °C · {battery_id} (measured)"))

    def _fill(self, table, rows):
        """rows = (iid, values) or (iid, values, tag); rows without a tag are zebra-striped."""
        table.delete(*table.get_children())
        for n, row in enumerate(rows):
            tag = row[2] if len(row) > 2 and row[2] else ("odd" if n % 2 else "even")
            table.insert("", "end", iid=row[0], values=row[1], tags=(tag,))

    @staticmethod
    def _reading_tag(row):
        """Highlight readings that are in the warning / critical range."""
        t = config.THRESHOLDS
        if row["sensor_type"] == "temperature":
            return "crit" if row["value"] >= t["temp_critical"] else "warn" if row["value"] >= t["temp_warning"] else None
        if row["sensor_type"] == "coolant_flow" and row["value"] < t["low_flow"]:
            return "warn"
        return None

    def refresh_readings(self):
        try:
            rows = self.db.read_all("sensor_readings")
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self._fill(self.reading_table, [(str(r["id"]), (r["id"], r["battery_id"], r["sensor_type"],
                                                         r["value"], r["unit"], r["timestamp"]),
                                         self._reading_tag(r)) for r in rows])

    def refresh_predictions(self):
        try:
            rows = self.db.read_all("predictions")
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self._fill(self.pred_table, [(str(r["id"]), (r["id"], r["battery_id"], r["model_name"],
                                                      r["predicted_temperature"], r["observed_temperature"],
                                                      r["abs_error"], r["pct_error"])) for r in rows])

    def refresh_cooling(self):
        try:
            rows = self.db.read_all("cfd_results")
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        cases, skipped = [], 0
        for r in rows:
            try:
                cases.append(case_from_row(r))
            except InvalidDataError:
                skipped += 1
        optimizer = CoolingOptimizer(cases)
        table_rows = optimizer.table()
        self._fill(self.cool_table, [(str(i), row, "good" if i == 0 and row[9] == "Yes" else
                                      "muted" if row[9] == "No" else None) for i, row in enumerate(table_rows)])
        bars = [(f"{r[1]} {r[2]:g}% Re{r[3]:g}" if r[2] else f"Water Re{r[3]:g}", r[7],
                 charts.COL["teal"] if r[9] == "Yes" else charts.COL["over"]) for r in table_rows]
        charts.draw_items(self.cool_canvas, charts.bar_chart(
            BAR_SIZE[0], BAR_SIZE[1], bars, "Performance index = h / pressure drop (higher is better, demo criterion)"))
        info = optimizer.summary()
        text = f"{info['cases']} cases, {info['feasible']} within {optimizer.temp_limit} C"
        if info["best"]:
            text += f" | best: {info['best'].case_name} (index {info['best'].performance_index():.2f})"
        if skipped:
            text += f" | {skipped} invalid rows skipped"
        self.best_label.config(text=text if cases else "No CFD cases stored - load the demo cases.")

    def refresh_history(self):
        try:
            battery_id = validate_battery_id(self.cell_var.get())
            cell = self.load_cell(battery_id)
            predicted = None
            if self.last_prediction and self.last_prediction[0] == battery_id:
                predicted = self.last_prediction[2]
            recs = recommend(cell, predicted)
            rows = self.db.read_all("sensor_readings", battery_id=battery_id)
            uniformity = ThermalAnalysis.uniformity(self.latest_temps())
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self._last_recs = recs
        self._fill(self.rec_table, [(str(i), (r.basis, r.alert_type, r.text),
                                     "crit" if r.severity >= 3 else "warn" if r.severity == 2 else
                                     "est" if r.basis == "Estimated" else "meas") for i, r in enumerate(recs)])
        self._fill(self.hist_table, [(str(r["id"]), (r["id"], r["sensor_type"], r["value"], r["unit"],
                                                      r["timestamp"])) for r in rows])
        temp = cell.process_readings().get("temperature")
        self.summary_label.config(text=f"Temp (measured): avg {temp['avg']}, max {temp['max']} C" if temp else "")
        if uniformity:
            delta, ok = uniformity
            self.uniform_label.config(text=f"Delta-T across batteries (measured, latest): {delta:.1f} C - "
                                           f"{'within' if ok else 'EXCEEDS'} the {config.THRESHOLDS['delta_t_target']} C target")
        else:
            self.uniform_label.config(text="Delta-T across batteries: needs readings from 2+ batteries")

    def refresh_maintenance(self):
        try:
            rows = self.db.read_all("maintenance_records")
        except BatteryTMSError as exc:
            self._show_error(exc)
            return
        self._fill(self.maint_table, [(str(r["id"]), (r["id"], r["battery_id"], r["alert_type"],
                                                       r["description"], r["timestamp"], r["status"]),
                                        "good" if r["status"] == "RESOLVED" else "warn") for r in rows])


def run():
    db = Database()
    app = App(db)
    app.mainloop()
    db.close()
