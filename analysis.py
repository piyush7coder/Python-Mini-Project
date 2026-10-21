"""Prediction models (abstract base class + implementations), digital-twin style
simulator, and prediction-error calculation.

All built-in predictors are DEMONSTRATION models, not validated AI."""
import pickle
from abc import ABC, abstractmethod
from datetime import datetime

from exceptions import (InsufficientDataError, ModelLoadError, PredictionError)

TWIN_DISCLAIMER = ("Software representation only - not a validated physical digital twin.")


class ThermalPredictor(ABC):
    """Abstract base class: every predictor forecasts the next temperature."""
    name = "Abstract"
    validated = False

    @abstractmethod
    def predict(self, temps, coolant_flow=None):
        """Return the estimated next temperature (deg C) from past temperatures."""

    def describe(self):
        status = "validated model" if self.validated else "demonstration model - not validated AI"
        return f"{self.name}: {status}; output is an estimate, not a measured value"


class MovingAveragePredictor(ThermalPredictor):
    name = "Moving Average"

    def __init__(self, window=3):
        self.window = window

    def predict(self, temps, coolant_flow=None):
        if not temps:
            raise InsufficientDataError("Need at least 1 temperature reading.")
        recent = temps[-self.window:]
        return sum(recent) / len(recent)


class LinearTrendPredictor(ThermalPredictor):
    """Least-squares straight line through the history, extrapolated one step."""
    name = "Linear Trend"

    def predict(self, temps, coolant_flow=None):
        n = len(temps)
        if n < 2:
            raise InsufficientDataError("Need at least 2 temperature readings.")
        mean_x, mean_y = (n - 1) / 2, sum(temps) / n
        denom = sum((x - mean_x) ** 2 for x in range(n))
        slope = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(temps)) / denom
        return mean_y + slope * (n - mean_x)


class RuleBasedPredictor(ThermalPredictor):
    """Last reading plus a rise that grows when coolant flow is low (demonstration rule)."""
    name = "Rule Based"

    def predict(self, temps, coolant_flow=None):
        if not temps:
            raise InsufficientDataError("Need at least 1 temperature reading.")
        rise = 0.5
        if coolant_flow is not None:
            rise = 3.0 if coolant_flow < 1.0 else 1.5 if coolant_flow < 2.0 else -0.5
        return temps[-1] + rise


class SavedModelPredictor(ThermalPredictor):
    """Wraps a trained model saved with pickle (any object with .predict([[...]])).
    Features: [latest temp, previous temp, coolant flow].
    SECURITY: only load model files you created or trust - pickle can run code."""

    def __init__(self, path, name="Saved Model"):
        self.name = name
        self.path = path
        try:
            with open(path, "rb") as f:
                self.model = pickle.load(f)
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError, ValueError) as exc:
            raise ModelLoadError(f"Could not load model '{path}': {exc}") from exc
        if not hasattr(self.model, "predict"):
            raise ModelLoadError(f"'{path}' does not contain a model with a predict() method.")

    def describe(self):
        return f"{self.name} (from {self.path}): validation status unknown; output is an estimate"

    def predict(self, temps, coolant_flow=None):
        if not temps:
            raise InsufficientDataError("Need at least 1 temperature reading.")
        prev = temps[-2] if len(temps) > 1 else temps[-1]
        flow = 0.0 if coolant_flow is None else coolant_flow
        try:
            return float(self.model.predict([[temps[-1], prev, flow]])[0])
        except Exception as exc:  # third-party model: any failure becomes PredictionError
            raise PredictionError(f"Saved model failed to predict: {exc}") from exc


PREDICTORS = {p.name: p for p in (MovingAveragePredictor(), LinearTrendPredictor(),
                                  RuleBasedPredictor())}


def prediction_error(predicted, observed):
    """Return (absolute_error, percent_error) between predicted and observed values."""
    abs_err = abs(predicted - observed)
    pct_err = (abs_err / abs(observed) * 100) if observed != 0 else 0.0
    return round(abs_err, 3), round(pct_err, 3)


class DigitalTwin:
    """Digital-twin-STYLE simulator: holds a virtual state synchronised from the
    latest readings, predicts the next state, and keeps a comparison history."""

    def __init__(self, battery_id, predictor):
        self.battery_id = battery_id
        self.predictor = predictor
        self.temps, self.flow, self.synced_at = [], None, None
        self.history = []          # list of comparison records

    def sync(self, cell):
        """Update the virtual state from a BatteryCell's latest sensor data."""
        temps = cell.values("temperature")
        if not temps:
            raise InsufficientDataError("No temperature readings to synchronise with.")
        self.temps, self.flow = list(temps), cell.latest("coolant_flow")
        self.synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def predict_next(self):
        return self.predictor.predict(self.temps, self.flow)

    def compare(self, predicted, observed):
        abs_err, pct_err = prediction_error(predicted, observed)
        record = {"battery_id": self.battery_id, "model": self.predictor.name,
                  "predicted": round(predicted, 2), "observed": observed,
                  "abs_error": abs_err, "pct_error": pct_err}
        self.history.append(record)
        return record
