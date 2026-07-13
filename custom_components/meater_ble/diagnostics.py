"""Diagnostics support for MEATER BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import MeaterConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": {"title": entry.title, "version": entry.version},
        "probe": {
            "address": coordinator.address,
            "name": coordinator.device_name,
            "data": coordinator.data.as_dict(),
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "last_notification": (
                coordinator._last_notification.isoformat()
                if coordinator._last_notification is not None
                else None
            ),
            "cook_history": [session.as_dict() for session in coordinator._history],
            "inference_settings": {
                "sample_window_seconds": 300,
                "ema_alpha": 0.18,
                "maximum_rejected_jump_c": 12.0,
                "insert_difference_c": 5.0,
                "insert_confirmation_seconds": 20,
                "remove_difference_c": 2.0,
                "remove_confirmation_seconds": 15,
                "rest_confirmation_seconds": 30,
                "rest_ambient_threshold_c": 35.0,
                "cooking_ambient_threshold_c": 40.0,
                "cooking_rate_threshold_c_per_min": 0.15,
            },
        },
    }
