# Changelog

## 0.9.1

### Fixed

- A probe in its charger or otherwise offline during Home Assistant startup no
  longer leaves the integration in setup retry with a red error border.
- The integration and entities load normally while the probe is offline.
- The integration reconnects automatically when the probe becomes available.
- Improved the expected offline status message.

## 0.9.0b1

First publishable beta.

- Local BLE through Home Assistant adapters and ESPHome proxies
- Automatic discovery, reconnect, and multiple probes
- Live temperature and battery notifications
- Friendly names and entity IDs
- Smoothed temperatures and heating rate
- Inferred inserted, cooking, cooling, resting, and removal states
- Cook event entity and persistent local cook history
- Diagnostics, confidence values, counters, and notification rate
- HACS metadata, validation workflows, issue forms, and release automation

Known limitations: only original MEATER and MEATER Plus are confirmed; inferred sessions may produce false transitions; one active BLE connection per probe.
