"""MEATER BLE integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_NAME
from .coordinator import MeaterCoordinator, default_probe_name

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
]

type MeaterConfigEntry = ConfigEntry[MeaterCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MeaterConfigEntry) -> bool:
    """Set up MEATER BLE from a config entry."""
    address = entry.data[CONF_ADDRESS]
    configured_name = entry.options.get(
        CONF_NAME,
        entry.data.get(CONF_NAME, default_probe_name(address)),
    )

    coordinator = MeaterCoordinator(
        hass=hass,
        address=address,
        name=configured_name,
    )

    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeaterConfigEntry) -> bool:
    """Unload a MEATER BLE config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.async_disconnect()

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
) -> None:
    """Reload after integration options change."""
    await hass.config_entries.async_reload(entry.entry_id)
