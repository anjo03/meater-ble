# MEATER BLE

Fully local Home Assistant support for original MEATER and MEATER Plus probes.

MEATER BLE connects directly through Home Assistant's Bluetooth stack, including ESPHome Bluetooth proxies. It does not require the MEATER mobile app, a MEATER account, or the MEATER cloud.

> **Public beta:** Raw temperature readings and BLE notifications are stable in current testing. Inserted, cooking, resting, and cook-session states are inferred and still need broader real-world validation.

## Features

- Automatic Bluetooth discovery
- Local Bluetooth adapters and ESPHome proxies
- Live GATT temperature notifications
- Multiple probes and friendly naming
- Automatic reconnect
- Raw and smoothed temperatures
- Heating rate
- Inserted, cooking, cooling, resting, and removal inference
- Cook lifecycle events
- Current cook statistics
- Persistent local history of the latest 25 inferred cooks
- Diagnostics and confidence values
- No cloud dependency or user-input controls

## Requirements

- Home Assistant 2026.3.0 or newer
- A connectable Bluetooth adapter or active ESPHome Bluetooth proxy
- Original MEATER or MEATER Plus probe

Other MEATER generations are not yet confirmed.

## Install with HACS

1. Open **HACS → Integrations**.
2. Open the menu and select **Custom repositories**.
3. Add `https://github.com/anjo03/esphome-meater`.
4. Select category **Integration**.
5. Install **MEATER BLE** and restart Home Assistant.
6. Open **Settings → Devices & services → Add integration → MEATER BLE**.

Remove the probe from its charger before setup.

## Manual installation

Copy `custom_components/meater_ble` to `/config/custom_components/meater_ble`, restart Home Assistant, and add **MEATER BLE** from Devices & services.

## ESPHome proxy

```yaml
esp32_ble_tracker:
  scan_parameters:
    active: true

bluetooth_proxy:
  active: true
```

Do not configure a probe MAC address or dedicated ESPHome `ble_client`.

## Main entities

- Tip and ambient temperature
- Smoothed tip and ambient temperature
- Heating rate
- Cook state
- Inserted, cooking, and resting
- Cook duration
- Maximum temperatures
- Average heating rate
- Last cook
- Cook event

Diagnostic entities are disabled by default: battery, RSSI, connection state, notification rate, and temperature difference.

Cook states: `idle`, `inserted`, `heating`, `cooling`, `resting`, `removed`.

Cook events: `inserted`, `removed`, `cooking_started`, `cooking_finished`, `resting_started`, `resting_finished`.

## Target-temperature automation

The integration deliberately has no target-temperature input. Use a normal automation:

```yaml
alias: MEATER reached 60°C
triggers:
  - trigger: numeric_state
    entity_id: sensor.bbq_probe_tip_temperature
    above: 60
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: MEATER
      message: The probe has reached 60°C.
mode: single
```

## Bluetooth limitation

The original probe allows one active Bluetooth connection. Close the MEATER app and prevent the Plus extender from connecting while Home Assistant uses the probe.

## Privacy

No data is sent externally. The latest 25 completed inferred sessions per probe are stored in Home Assistant's local `.storage` directory.

## Offline behavior

A MEATER probe is normally offline while stored in its charger. MEATER BLE
loads normally in that state:

- The config entry does not show a red setup error.
- Entities remain registered and show unavailable while the probe is offline.
- The connection diagnostic entity is off.
- The integration reconnects automatically when the probe is removed from the charger.

## Troubleshooting

If discovery fails, remove the probe from its charger, close the app, temporarily remove the extender battery, verify the proxy supports active Bluetooth, and move the probe closer.

For bug reports, include Home Assistant version, integration version, probe model, proxy/adapter details, downloaded diagnostics, and relevant logs. Remove private information.

## Disclaimer

This independent community project is not affiliated with, endorsed by, or supported by Apption Labs or MEATER. Product names and artwork belong to their respective owners.

## License

MIT
