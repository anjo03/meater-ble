"""Base entity for MEATER BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import MeaterConfigEntry
from .const import DOMAIN
from .coordinator import MeaterCoordinator


class MeaterEntity(CoordinatorEntity[MeaterCoordinator]):
    """Base class for MEATER BLE entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: MeaterConfigEntry, key: str) -> None:
        """Initialize a MEATER entity."""
        super().__init__(entry.runtime_data)
        # Keep the MAC-based unique ID stable, but ask Home Assistant to use
        # the friendly probe name when generating the initial entity ID.
        self._attr_unique_id = f"{entry.runtime_data.address}_{key}"
        self._attr_suggested_object_id = (
            f"{slugify(entry.runtime_data.device_name)}_{key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return current device metadata."""
        data = self.coordinator.data

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.address)},
            connections={("bluetooth", self.coordinator.address)},
            name=self.coordinator.device_name,
            manufacturer=data.manufacturer or "Apption Labs",
            model=data.model or "MEATER",
            serial_number=data.serial_number,
            sw_version=data.firmware_version,
            hw_version=data.hardware_version,
        )
