"""Cooling performance analysis (brief Scenarios 2 and 3): abstract cooling-fluid
class with Water / Nanofluid subclasses, thermal analysis helpers, and a ranking
optimizer using filter, map, sorted and lambda.

The ranking index is a DEMONSTRATION criterion, not a validated physical law."""
import math
from abc import ABC, abstractmethod

import config
from exceptions import InvalidDataError


def _positive(name, value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InvalidDataError(f"{name} must be a number (got {value!r}).")
    if math.isnan(number) or number <= 0:
        raise InvalidDataError(f"{name} must be a positive number (got {value!r}).")
    return number


class CoolingFluid(ABC):
    """Common base class for cooling cases; subclasses override performance_index()."""
    fluid_name = "Fluid"

    def __init__(self, reynolds_number, inlet_temperature, concentration,
                 pressure_drop, heat_transfer_coefficient, max_temperature, case_name=""):
        self.reynolds_number = _positive("Reynolds number", reynolds_number)
        self.inlet_temperature = float(inlet_temperature)
        self.concentration = float(concentration or 0.0)      # % by volume
        self.pressure_drop = _positive("Pressure drop", pressure_drop)  # Pa
        self.heat_transfer_coefficient = _positive("Heat-transfer coefficient",
                                                   heat_transfer_coefficient)  # W/m2K
        self.max_temperature = float(max_temperature)          # C
        self.case_name = case_name

    @abstractmethod
    def performance_index(self):
        """Thermal benefit per unit pumping penalty (higher is better)."""

    def thermal_benefit(self, baseline_max_temp):
        return baseline_max_temp - self.max_temperature

    def meets_target(self, limit):
        return self.max_temperature <= limit


class WaterCoolant(CoolingFluid):
    fluid_name = "Water"

    def performance_index(self):
        return self.heat_transfer_coefficient / self.pressure_drop


class NanofluidCoolant(CoolingFluid):
    fluid_name = "Al2O3/water"

    def performance_index(self):
        # Same h/dP ratio, with a demonstration penalty for particle loading.
        base = self.heat_transfer_coefficient / self.pressure_drop
        return base / (1 + self.concentration / 100)


def case_from_row(row):
    """Build the right CoolingFluid subclass from a cfd_results database row."""
    conc = row.get("nanoparticle_concentration") or 0
    cls = NanofluidCoolant if float(conc) > 0 else WaterCoolant
    return cls(row["reynolds_number"], row["inlet_temperature"], conc, row["pressure_drop"],
               row["heat_transfer_coefficient"], row["max_temperature"], row.get("case_name", ""))


class ThermalAnalysis:
    """Temperature-difference helpers."""

    @staticmethod
    def delta_t(a, b):
        return abs(a - b)

    @staticmethod
    def coolant_delta_t(inlet, outlet):
        return outlet - inlet

    @staticmethod
    def uniformity(temps_by_battery):
        """Return (delta_t, within_target) across batteries, or None if fewer than 2."""
        temps = list(temps_by_battery.values())
        if len(temps) < 2:
            return None
        delta = max(temps) - min(temps)
        return delta, delta < config.THRESHOLDS["delta_t_target"]


class CoolingOptimizer:
    """Ranks candidate cooling cases: feasible cases (max temp within limit) first,
    then by descending performance index."""

    def __init__(self, cases, temp_limit=None):
        self.cases = list(cases)
        self.temp_limit = temp_limit if temp_limit is not None else config.THRESHOLDS["temp_warning"]

    def feasible(self):
        return list(filter(lambda c: c.meets_target(self.temp_limit), self.cases))

    def ranked(self):
        return sorted(self.cases,
                      key=lambda c: (not c.meets_target(self.temp_limit), -c.performance_index()))

    def _water_baseline(self, reynolds):
        match = list(filter(lambda c: c.fluid_name == "Water" and c.reynolds_number == reynolds,
                            self.cases))
        return match[0] if match else None

    def summary(self):
        indices = list(map(lambda c: c.performance_index(), self.cases))
        ranked = self.ranked()
        return {"cases": len(self.cases), "feasible": len(self.feasible()),
                "mean_index": round(sum(indices) / len(indices), 3) if indices else None,
                "best": ranked[0] if ranked and ranked[0].meets_target(self.temp_limit) else None}

    def table(self):
        rows = []
        for rank, c in enumerate(self.ranked(), start=1):
            base = self._water_baseline(c.reynolds_number)
            benefit = "-" if c.fluid_name == "Water" or base is None else \
                f"{c.thermal_benefit(base.max_temperature):.1f}"
            rows.append((rank, c.fluid_name, c.concentration, c.reynolds_number, c.max_temperature,
                         c.pressure_drop, c.heat_transfer_coefficient,
                         round(c.performance_index(), 3), benefit,
                         "Yes" if c.meets_target(self.temp_limit) else "No"))
        return rows
