"""Event entity for inferred MEATER probe transitions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeaterConfigEntry
from .entity import MeaterEntity

EVENT_TYPES = [
    "inserted",
    "removed",
    "cooking_started",
    "cooking_finished",
    "resting_started",
    "resting_finished",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MEATER event entity."""
    async_add_entities([MeaterCookEvent(entry)])


class MeaterCookEvent(MeaterEntity, EventEntity):
    """Event entity for inferred probe and cooking transitions."""

    _attr_event_types = EVENT_TYPES
    _attr_translation_key = "cook_event"
    _attr_icon = "mdi:chef-hat"

    def __init__(self, entry: MeaterConfigEntry) -> None:
        """Initialize the event entity."""
        super().__init__(entry, "cook_event")
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator events."""
        await super().async_added_to_hass()
        self._remove_listener = self.coordinator.add_event_listener(
            self._handle_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove the coordinator event subscription."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_event(
        self,
        event_type: str,
        event_attributes: dict[str, Any],
    ) -> None:
        """Publish an inferred event."""
        self._trigger_event(event_type, event_attributes)
        self.async_write_ha_state()
