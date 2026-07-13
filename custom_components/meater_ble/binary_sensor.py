"""Binary sensor entities for MEATER BLE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeaterConfigEntry
from .entity import MeaterEntity
from .models import MeaterData


@dataclass(frozen=True, kw_only=True)
class MeaterBinaryDescription(BinarySensorEntityDescription):
    """Description of a MEATER binary sensor."""

    value_fn: Callable[[MeaterData], bool]


BINARY_SENSORS: tuple[MeaterBinaryDescription, ...] = (
    MeaterBinaryDescription(
        key="inserted",
        translation_key="inserted",
        icon="mdi:thermometer-probe",
        value_fn=lambda data: data.inserted,
    ),
    MeaterBinaryDescription(
        key="cooking",
        translation_key="cooking",
        icon="mdi:grill",
        value_fn=lambda data: data.cooking,
    ),
    MeaterBinaryDescription(
        key="resting",
        translation_key="resting",
        icon="mdi:food-steak",
        value_fn=lambda data: data.resting,
    ),
    MeaterBinaryDescription(
        key="connected",
        translation_key="connected",
        icon="mdi:bluetooth-connect",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MEATER binary sensors."""
    async_add_entities(
        MeaterBinarySensor(entry, description)
        for description in BINARY_SENSORS
    )


class MeaterBinarySensor(MeaterEntity, BinarySensorEntity):
    """Representation of a MEATER binary sensor."""

    entity_description: MeaterBinaryDescription

    def __init__(
        self,
        entry: MeaterConfigEntry,
        description: MeaterBinaryDescription,
    ) -> None:
        """Initialize a binary sensor."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the current state."""
        return self.entity_description.value_fn(self.coordinator.data)
