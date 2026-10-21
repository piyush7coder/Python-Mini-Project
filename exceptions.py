"""Custom exceptions for the Battery Thermal Management System."""


class BatteryTMSError(Exception):
    """Base class for all application errors."""


class InvalidIdentifierError(BatteryTMSError):
    """Battery ID or status string is malformed."""


class InvalidSensorValueError(BatteryTMSError):
    """Sensor type unknown, reading missing/not numeric/NaN, or out of physical range."""


class DatabaseOperationError(BatteryTMSError):
    """An SQLite operation failed."""


class RecordNotFoundError(BatteryTMSError):
    """Requested database record does not exist."""


class InsufficientDataError(BatteryTMSError):
    """Not enough readings available to make a prediction."""


class ModelLoadError(BatteryTMSError):
    """A saved prediction model could not be loaded."""


class PredictionError(BatteryTMSError):
    """A loaded model failed while predicting."""


class InvalidDataError(BatteryTMSError):
    """A cooling/CFD case contains invalid numbers."""


class ConfigError(BatteryTMSError):
    """Invalid threshold configuration."""
