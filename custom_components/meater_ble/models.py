"""Data models for MEATER BLE."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CookSession:
    """One automatically inferred cook session."""

    started_at: str
    finished_at: str | None = None
    duration_seconds: int | None = None
    maximum_tip_temperature: float | None = None
    maximum_ambient_temperature: float | None = None
    average_heating_rate: float | None = None
    sample_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Return serializable session data."""
        return asdict(self)


@dataclass(slots=True)
class MeaterData:
    """Latest data read or inferred from a MEATER probe."""

    tip_temperature: float | None = None
    ambient_temperature: float | None = None
    smoothed_tip_temperature: float | None = None
    smoothed_ambient_temperature: float | None = None
    battery: int | None = None
    rssi: int | None = None
    connected: bool = False

    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    firmware_version: str | None = None
    hardware_version: str | None = None

    transport: str = "polling"
    notifications_active: bool = False
    notification_rate: float | None = None
    reconnect_count: int = 0
    read_failure_count: int = 0
    rejected_sample_count: int = 0
    last_error: str | None = None

    inserted: bool = False
    cooking: bool = False
    resting: bool = False
    cook_state: str = "idle"
    heating_rate: float | None = None
    temperature_difference: float | None = None
    rate_samples: int = 0
    rate_confidence: float = 0.0
    inserted_confidence: float = 0.0
    cooking_confidence: float = 0.0
    last_transition_reason: str | None = None
    last_cook_event: str | None = None

    cook_duration_seconds: int | None = None
    maximum_tip_temperature: float | None = None
    maximum_ambient_temperature: float | None = None
    average_heating_rate: float | None = None
    current_session_sample_count: int = 0
    last_cook: dict[str, Any] | None = field(default=None)

    def as_dict(self) -> dict[str, Any]:
        """Return diagnostics-friendly data."""
        return asdict(self)
