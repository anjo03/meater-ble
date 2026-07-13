"""Sensor entities for MEATER BLE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeaterConfigEntry
from .entity import MeaterEntity
from .models import MeaterData


@dataclass(frozen=True, kw_only=True)
class MeaterSensorDescription(SensorEntityDescription):
    """Description of a MEATER sensor."""

    value_fn: Callable[[MeaterData], float | int | str | None]
    attributes_fn: Callable[[MeaterData], dict[str, Any] | None] | None = None


SENSORS: tuple[MeaterSensorDescription, ...] = (
    MeaterSensorDescription(
        key="tip_temperature",
        translation_key="tip_temperature",
        icon="mdi:thermometer-probe",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.tip_temperature,
    ),
    MeaterSensorDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        icon="mdi:grill",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.ambient_temperature,
    ),
    MeaterSensorDescription(
        key="smoothed_tip_temperature",
        translation_key="smoothed_tip_temperature",
        icon="mdi:chart-bell-curve-cumulative",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.smoothed_tip_temperature,
    ),
    MeaterSensorDescription(
        key="smoothed_ambient_temperature",
        translation_key="smoothed_ambient_temperature",
        icon="mdi:chart-bell-curve",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.smoothed_ambient_temperature,
    ),
    MeaterSensorDescription(
        key="heating_rate",
        translation_key="heating_rate",
        icon="mdi:chart-timeline-variant",
        native_unit_of_measurement="°C/min",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.heating_rate,
    ),
    MeaterSensorDescription(
        key="cook_state",
        translation_key="cook_state",
        icon="mdi:chef-hat",
        value_fn=lambda data: data.cook_state,
        attributes_fn=lambda data: {
            "transition_reason": data.last_transition_reason,
            "inserted_confidence": data.inserted_confidence,
            "cooking_confidence": data.cooking_confidence,
            "rate_confidence": data.rate_confidence,
        },
    ),
    MeaterSensorDescription(
        key="cook_duration",
        translation_key="cook_duration",
        icon="mdi:timer-outline",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.cook_duration_seconds,
    ),
    MeaterSensorDescription(
        key="maximum_tip_temperature",
        translation_key="maximum_tip_temperature",
        icon="mdi:thermometer-high",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.maximum_tip_temperature,
    ),
    MeaterSensorDescription(
        key="maximum_ambient_temperature",
        translation_key="maximum_ambient_temperature",
        icon="mdi:heat-wave",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.maximum_ambient_temperature,
    ),
    MeaterSensorDescription(
        key="average_heating_rate",
        translation_key="average_heating_rate",
        icon="mdi:chart-line",
        native_unit_of_measurement="°C/min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.average_heating_rate,
    ),
    MeaterSensorDescription(
        key="last_cook",
        translation_key="last_cook",
        icon="mdi:history",
        value_fn=lambda data: (
            data.last_cook.get("finished_at") if data.last_cook else None
        ),
        attributes_fn=lambda data: data.last_cook,
    ),
    MeaterSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery,
    ),
    MeaterSensorDescription(
        key="rssi",
        translation_key="rssi",
        icon="mdi:bluetooth",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.rssi,
    ),
    MeaterSensorDescription(
        key="notification_rate",
        translation_key="notification_rate",
        icon="mdi:pulse",
        native_unit_of_measurement="updates/s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.notification_rate,
    ),
    MeaterSensorDescription(
        key="temperature_difference",
        translation_key="temperature_difference",
        icon="mdi:delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.temperature_difference,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(MeaterSensor(entry, description) for description in SENSORS)


class MeaterSensor(MeaterEntity, SensorEntity):
    entity_description: MeaterSensorDescription

    def __init__(self, entry: MeaterConfigEntry, description: MeaterSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
