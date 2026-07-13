"""Config flow for MEATER BLE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS

from .const import CONF_NAME, DOMAIN, MEATER_SERVICE_UUID
from .coordinator import default_probe_name


def _is_meater(service_info: BluetoothServiceInfoBleak) -> bool:
    """Return whether discovery information looks like a MEATER probe."""
    service_uuids = {uuid.lower() for uuid in service_info.service_uuids}
    return (
        MEATER_SERVICE_UUID in service_uuids
        or "meater" in (service_info.name or "").lower()
    )


class MeaterBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MEATER BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}
        self._selected_address: str | None = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return MeaterBleOptionsFlow(config_entry)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if not _is_meater(discovery_info):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._selected_address = discovery_info.address
        default_name = default_probe_name(discovery_info.address)

        # Keep the discovery card clean. The MAC remains available in the
        # confirmation dialog and as the stable internal identifier.
        self.context["title_placeholders"] = {"name": "MEATER probe"}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and name a discovered probe."""
        assert self._selected_address is not None

        address = self._selected_address
        suggested_name = default_probe_name(address)

        if user_input is not None:
            name = user_input[CONF_NAME].strip() or suggested_name
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=suggested_name): str,
                }
            ),
            description_placeholders={
                "name": suggested_name,
                "address": address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow manual selection from currently discovered MEATER probes."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            self._selected_address = address
            return await self.async_step_name()

        configured = self._async_current_ids(include_ignore=False)

        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if service_info.address in configured:
                continue
            if _is_meater(service_info):
                self._discovered[service_info.address] = service_info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        choices = {
            address: default_probe_name(address)
            for address in self._discovered
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(choices),
                }
            ),
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name a manually selected probe."""
        assert self._selected_address is not None

        address = self._selected_address
        suggested_name = default_probe_name(address)

        if user_input is not None:
            name = user_input[CONF_NAME].strip() or suggested_name
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=suggested_name): str,
                }
            ),
            description_placeholders={
                "name": suggested_name,
                "address": address,
            },
        )


class MeaterBleOptionsFlow(OptionsFlow):
    """Handle MEATER BLE options."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename the probe."""
        current_name = self._config_entry.options.get(
            CONF_NAME,
            self._config_entry.data.get(
                CONF_NAME,
                default_probe_name(self._config_entry.data[CONF_ADDRESS]),
            ),
        )

        if user_input is not None:
            name = user_input[CONF_NAME].strip() or current_name
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                title=name,
            )
            return self.async_create_entry(
                title="",
                data={CONF_NAME: name},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=current_name): str,
                }
            ),
        )
