"""Rule-based cooling recommendations (decision support only).
Every recommendation is tagged 'Measured' (actual sensor data) or 'Estimated'
(model prediction) so the two are never confused. These rules are DEMONSTRATION
rules and must never be connected to physical cooling controls."""
from dataclasses import dataclass

import config

DISCLAIMER = ("Decision support only - demonstration rules. Not connected to any "
              "physical cooling control.")


@dataclass
class Recommendation:
    basis: str            # "Measured" or "Estimated"
    text: str
    alert_type: str = "INFO"
    severity: int = 0


def recommend(cell, predicted=None):
    """Return a list of Recommendation objects for a BatteryCell.

    Reviews latest temperature, coolant flow, recent temperature trend and (optionally)
    a model-estimated next temperature."""
    t = config.THRESHOLDS
    temp, flow = cell.latest("temperature"), cell.latest("coolant_flow")
    if temp is None:
        return [Recommendation("Measured", "No temperature readings yet - add data first.", "NO_DATA")]

    recs = []
    if temp >= t["temp_critical"]:
        recs.append(Recommendation(
            "Measured", f"CRITICAL: {temp} C. Reduce load/charging, raise coolant flow and "
                        "inspect the battery.", "OVERHEAT", 3))
    elif temp >= t["temp_warning"]:
        recs.append(Recommendation(
            "Measured", f"Elevated temperature {temp} C. Increase coolant flow rate.", "HIGH_TEMP", 2))
    elif temp < t["temp_min"]:
        recs.append(Recommendation(
            "Measured", f"Temperature {temp} C is below the {t['temp_min']}-{t['temp_warning']} C "
                        "target range. Review operating conditions.", "LOW_TEMP", 1))
    else:
        recs.append(Recommendation("Measured", f"Temperature {temp} C is within range. Keep monitoring."))

    if flow is None:
        recs.append(Recommendation("Measured", "No coolant flow reading - add a coolant_flow value.",
                                   "NO_FLOW_DATA", 1))
    elif flow < t["low_flow"]:
        recs.append(Recommendation(
            "Measured", f"Low coolant flow ({flow} L/min). Inspect pump and microchannel for blockage.",
            "LOW_FLOW", 2))

    trend = cell.temperature_trend()
    if trend is not None and trend >= t["rapid_rise"]:
        recs.append(Recommendation(
            "Measured", f"Temperature rising about {trend:.1f} C per reading - review the thermal gradient.",
            "RAPID_RISE", 2))

    if predicted is not None:
        if predicted >= t["temp_critical"]:
            recs.append(Recommendation("Estimated", f"Model estimates {predicted:.1f} C next - "
                                       "act now to prevent overheating.", "PREDICTED_RISK", 3))
        elif predicted >= t["temp_warning"]:
            recs.append(Recommendation("Estimated", f"Model estimates {predicted:.1f} C next - "
                                       "increase cooling before it rises.", "PREDICTED_RISK", 2))
        else:
            recs.append(Recommendation("Estimated", f"Model estimates {predicted:.1f} C next - "
                                       "within the safe range."))
    return recs


def most_severe(recs):
    return max(recs, key=lambda r: r.severity)
