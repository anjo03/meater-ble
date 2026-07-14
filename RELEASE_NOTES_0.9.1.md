# MEATER BLE 0.9.1

MEATER BLE now treats a probe in its charger as a normal offline state during
Home Assistant startup. The integration loads without a red error border,
keeps its entities registered, and reconnects automatically when the probe is
removed from the charger.
