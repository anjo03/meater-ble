# Publishing checklist

Repository description:

```text
Local Bluetooth integration for MEATER probes in Home Assistant, with ESPHome proxy support and no cloud dependency.
```

Repository topics:

```text
home-assistant
hacs
bluetooth
ble
esphome
meater
meater-plus
custom-integration
local-control
```

Ensure the repository is public and Issues and Actions are enabled.

Push the package, wait for **Validate** to pass, then create the beta release:

```bash
git tag v0.9.0b1
git push origin v0.9.0b1
```

The release workflow checks the manifest version, builds a manual-install archive, and creates a GitHub prerelease.

Test installation and upgrading through HACS as a custom repository before requesting inclusion in the default HACS catalog.
