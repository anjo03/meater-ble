"""Bluetooth coordinator, inference engine, and cook history for MEATER BLE."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Final

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_POLL_INTERVAL,
    BATTERY_CHARACTERISTIC_UUID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FIRMWARE_REVISION_UUID,
    HARDWARE_REVISION_UUID,
    IDLE_POLL_INTERVAL,
    MANUFACTURER_NAME_UUID,
    MODEL_NUMBER_UUID,
    NOTIFICATION_WATCHDOG_INTERVAL,
    SERIAL_NUMBER_UUID,
    TEMPERATURE_CHARACTERISTIC_UUID,
)
from .models import CookSession, MeaterData

_LOGGER = logging.getLogger(__name__)

CONNECTION_TIMEOUT: Final = 20.0
READ_ATTEMPTS: Final = 2
MAC_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$", re.IGNORECASE)

PUBLISH_INTERVAL: Final = timedelta(seconds=2)
SAMPLE_WINDOW: Final = timedelta(minutes=5)
RATE_MIN_SPAN: Final = timedelta(seconds=60)
INSERT_CONFIRM: Final = timedelta(seconds=20)
REMOVE_CONFIRM: Final = timedelta(seconds=15)
REST_CONFIRM: Final = timedelta(seconds=30)
INSERT_DIFFERENCE_C: Final = 5.0
REMOVE_DIFFERENCE_C: Final = 2.0
COOK_AMBIENT_C: Final = 40.0
COOK_RATE_C_PER_MIN: Final = 0.15
COOLING_RATE_C_PER_MIN: Final = -0.15
REST_AMBIENT_C: Final = 35.0
MAX_SAMPLE_JUMP_C: Final = 12.0
EMA_ALPHA: Final = 0.18
HISTORY_LIMIT: Final = 25
STORAGE_VERSION: Final = 1


@dataclass(slots=True)
class TemperatureSample:
    """One temperature sample used by the inference engine."""

    timestamp: datetime
    tip: float
    ambient: float


def default_probe_name(address: str) -> str:
    """Create a stable user-facing name for a probe."""
    return f"MEATER {address.replace(':', '')[-6:].upper()}"


class MeaterCoordinator(DataUpdateCoordinator[MeaterData]):
    """Read one MEATER probe and infer physical/cook state."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.address = address
        self.device_name = (
            default_probe_name(address)
            if not name or MAC_PATTERN.fullmatch(name)
            else name
        )

        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._metadata_loaded = False
        self._notifications_active = False
        self._last_notification: datetime | None = None
        self._notification_times: deque[datetime] = deque()
        self._last_publish: datetime | None = None
        self._reconnect_count = 0
        self._read_failure_count = 0
        self._rejected_sample_count = 0
        self._last_error: str | None = None

        self._samples: deque[TemperatureSample] = deque()
        self._insert_candidate_since: datetime | None = None
        self._remove_candidate_since: datetime | None = None
        self._rest_candidate_since: datetime | None = None
        self._event_listeners: list[Callable[[str, dict[str, Any]], None]] = []

        storage_key = address.replace(":", "").lower()
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{storage_key}",
        )
        self._history: list[CookSession] = []
        self._active_session: CookSession | None = None
        self._active_session_rate_total = 0.0
        self._active_session_rate_samples = 0

        self.data = MeaterData(manufacturer="Apption Labs", model="MEATER")

    async def async_initialize(self) -> None:
        """Load persistent cook history."""
        stored = await self._store.async_load()
        if not stored:
            return

        self._history = [
            CookSession(**item)
            for item in stored.get("history", [])
            if isinstance(item, dict)
        ][-HISTORY_LIMIT:]

        if self._history:
            self.data.last_cook = self._history[-1].as_dict()

    @callback
    def add_event_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Subscribe to inferred events."""
        self._event_listeners.append(listener)

        def remove() -> None:
            if listener in self._event_listeners:
                self._event_listeners.remove(listener)

        return remove

    async def _async_update_data(self) -> MeaterData:
        """Connect through the best adapter/proxy and update the probe."""
        async with self._connect_lock:
            last_error: Exception | None = None

            for attempt in range(1, READ_ATTEMPTS + 1):
                try:
                    return await self._async_read_once()
                except (BleakError, TimeoutError, EOFError) as err:
                    last_error = err
                    self._read_failure_count += 1
                    self._last_error = str(err)
                    _LOGGER.debug(
                        "MEATER read attempt %s/%s failed for %s",
                        attempt,
                        READ_ATTEMPTS,
                        self.address,
                        exc_info=True,
                    )
                    self.data.connected = False
                    await self.async_disconnect()

            raise UpdateFailed(
                f"Unable to read MEATER probe after {READ_ATTEMPTS} attempts: "
                f"{last_error}"
            ) from last_error

    async def _async_read_once(self) -> MeaterData:
        """Read from the current connection or establish a new one."""
        ble_device = None
        newly_connected = False

        if self._client is None or not self._client.is_connected:
            ble_device = async_ble_device_from_address(
                self.hass,
                self.address,
                connectable=True,
            )
            if ble_device is None:
                self.data.connected = False
                raise UpdateFailed(
                    f"MEATER {self.address} is not currently visible over Bluetooth"
                )

            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.device_name,
                self._disconnected,
                max_attempts=3,
            )
            newly_connected = True
            self._reconnect_count += 1

        if newly_connected:
            if not self._metadata_loaded:
                await self._async_read_metadata()
            await self._async_enable_notifications()

        temperature_payload = await asyncio.wait_for(
            self._client.read_gatt_char(TEMPERATURE_CHARACTERISTIC_UUID),
            timeout=CONNECTION_TIMEOUT,
        )
        battery_payload = await asyncio.wait_for(
            self._client.read_gatt_char(BATTERY_CHARACTERISTIC_UUID),
            timeout=CONNECTION_TIMEOUT,
        )

        tip, ambient = _decode_temperatures(bytes(temperature_payload))
        battery = _decode_battery(bytes(battery_payload))
        rssi = self.data.rssi
        if ble_device is not None:
            rssi = getattr(ble_device, "rssi", rssi)

        result = self._process_temperature(
            tip=tip,
            ambient=ambient,
            battery=battery,
            rssi=rssi,
        )
        self._last_error = None
        return result

    async def _async_enable_notifications(self) -> None:
        """Subscribe to notifications when supported."""
        assert self._client is not None

        temperature_ok = False
        battery_ok = False

        try:
            await self._client.start_notify(
                TEMPERATURE_CHARACTERISTIC_UUID,
                self._temperature_notification,
            )
            temperature_ok = True
        except (BleakError, ValueError, AttributeError):
            _LOGGER.debug("Temperature notifications unavailable", exc_info=True)

        try:
            await self._client.start_notify(
                BATTERY_CHARACTERISTIC_UUID,
                self._battery_notification,
            )
            battery_ok = True
        except (BleakError, ValueError, AttributeError):
            _LOGGER.debug("Battery notifications unavailable", exc_info=True)

        self._notifications_active = temperature_ok
        self.update_interval = (
            NOTIFICATION_WATCHDOG_INTERVAL
            if temperature_ok
            else DEFAULT_SCAN_INTERVAL
        )

        _LOGGER.info(
            "MEATER %s transport: %s (temperature notify=%s, battery notify=%s)",
            self.address,
            "notifications with polling watchdog"
            if temperature_ok
            else "adaptive polling",
            temperature_ok,
            battery_ok,
        )

    @callback
    def _temperature_notification(self, _characteristic, payload: bytearray) -> None:
        """Process every notification and publish at most every two seconds."""
        try:
            tip, ambient = _decode_temperatures(bytes(payload))
        except UpdateFailed:
            _LOGGER.warning("Ignoring invalid temperature notification", exc_info=True)
            return

        now = datetime.now(timezone.utc)
        self._last_notification = now
        self._notification_times.append(now)
        cutoff = now - timedelta(seconds=30)
        while self._notification_times and self._notification_times[0] < cutoff:
            self._notification_times.popleft()

        result = self._process_temperature(
            tip=tip,
            ambient=ambient,
            battery=self.data.battery,
            rssi=self.data.rssi,
            now=now,
        )

        if self._last_publish is None or now - self._last_publish >= PUBLISH_INTERVAL:
            self._last_publish = now
            self.async_set_updated_data(result)

    @callback
    def _battery_notification(self, _characteristic, payload: bytearray) -> None:
        """Process a battery notification."""
        try:
            self.data.battery = _decode_battery(bytes(payload))
        except UpdateFailed:
            _LOGGER.warning("Ignoring invalid battery notification")
            return

        self._last_notification = datetime.now(timezone.utc)

    def _process_temperature(
        self,
        *,
        tip: float,
        ambient: float,
        battery: int | None,
        rssi: int | None,
        now: datetime | None = None,
    ) -> MeaterData:
        """Filter, smooth, calculate statistics, and infer state."""
        now = now or datetime.now(timezone.utc)

        if self._is_implausible_sample(tip, ambient):
            self._rejected_sample_count += 1
            return self.data

        smooth_tip = self._ema(self.data.smoothed_tip_temperature, tip)
        smooth_ambient = self._ema(self.data.smoothed_ambient_temperature, ambient)

        self._samples.append(TemperatureSample(now, smooth_tip, smooth_ambient))
        cutoff = now - SAMPLE_WINDOW
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

        rate, rate_confidence, samples_used = self._calculate_rate()
        difference = smooth_ambient - smooth_tip

        previous_state = self.data.cook_state
        previous_inserted = self.data.inserted
        previous_cooking = self.data.cooking
        previous_resting = self.data.resting

        inserted, inserted_confidence = self._calculate_inserted(now, difference)
        state, reason, cooking_confidence = self._calculate_cook_state(
            now=now,
            inserted=inserted,
            ambient=smooth_ambient,
            rate=rate,
        )
        cooking = state == "heating"
        resting = state == "resting"

        self._update_session(
            now=now,
            cooking=cooking,
            tip=smooth_tip,
            ambient=smooth_ambient,
            rate=rate,
        )

        notification_rate = self._calculate_notification_rate()
        result = MeaterData(
            tip_temperature=tip,
            ambient_temperature=ambient,
            smoothed_tip_temperature=round(smooth_tip, 2),
            smoothed_ambient_temperature=round(smooth_ambient, 2),
            battery=battery,
            rssi=rssi,
            connected=True,
            manufacturer=self.data.manufacturer,
            model=self.data.model,
            serial_number=self.data.serial_number,
            firmware_version=self.data.firmware_version,
            hardware_version=self.data.hardware_version,
            transport=(
                "notifications+watchdog"
                if self._notifications_active
                else "adaptive_polling"
            ),
            notifications_active=self._notifications_active,
            notification_rate=notification_rate,
            reconnect_count=self._reconnect_count,
            read_failure_count=self._read_failure_count,
            rejected_sample_count=self._rejected_sample_count,
            last_error=self._last_error,
            inserted=inserted,
            cooking=cooking,
            resting=resting,
            cook_state=state,
            heating_rate=rate,
            temperature_difference=round(difference, 2),
            rate_samples=samples_used,
            rate_confidence=rate_confidence,
            inserted_confidence=inserted_confidence,
            cooking_confidence=cooking_confidence,
            last_transition_reason=(
                reason if state != previous_state else self.data.last_transition_reason
            ),
            last_cook_event=self.data.last_cook_event,
            cook_duration_seconds=self._current_duration(now),
            maximum_tip_temperature=(
                self._active_session.maximum_tip_temperature
                if self._active_session else None
            ),
            maximum_ambient_temperature=(
                self._active_session.maximum_ambient_temperature
                if self._active_session else None
            ),
            average_heating_rate=self._current_average_rate(),
            current_session_sample_count=(
                self._active_session.sample_count if self._active_session else 0
            ),
            last_cook=(
                self._history[-1].as_dict() if self._history else self.data.last_cook
            ),
        )
        self.data = result
        self._apply_adaptive_interval(result)

        if inserted != previous_inserted:
            self._emit_event("inserted" if inserted else "removed", result)
        if cooking and not previous_cooking:
            self._emit_event("cooking_started", result)
        elif previous_cooking and not cooking:
            self._emit_event("cooking_finished", result)
        if resting and not previous_resting:
            self._emit_event("resting_started", result)
        elif previous_resting and not resting:
            self._emit_event("resting_finished", result)

        if state != previous_state:
            _LOGGER.info(
                "MEATER %s state changed: %s -> %s (%s)",
                self.address,
                previous_state,
                state,
                reason,
            )

        return result

    def _is_implausible_sample(self, tip: float, ambient: float) -> bool:
        """Reject isolated impossible jumps while preserving real changes."""
        if self.data.tip_temperature is None or self.data.ambient_temperature is None:
            return False

        tip_jump = abs(tip - self.data.tip_temperature)
        ambient_jump = abs(ambient - self.data.ambient_temperature)
        return tip_jump > MAX_SAMPLE_JUMP_C and ambient_jump > MAX_SAMPLE_JUMP_C

    @staticmethod
    def _ema(previous: float | None, current: float) -> float:
        """Calculate an exponential moving average."""
        if previous is None:
            return current
        return previous + EMA_ALPHA * (current - previous)

    def _calculate_inserted(
        self, now: datetime, difference: float
    ) -> tuple[bool, float]:
        """Infer insertion with confirmation and confidence."""
        if not self.data.inserted:
            if difference >= INSERT_DIFFERENCE_C:
                self._insert_candidate_since = self._insert_candidate_since or now
                elapsed = (now - self._insert_candidate_since).total_seconds()
                confidence = min(1.0, elapsed / INSERT_CONFIRM.total_seconds())
                if now - self._insert_candidate_since >= INSERT_CONFIRM:
                    self._remove_candidate_since = None
                    return True, 1.0
                return False, round(confidence, 2)

            self._insert_candidate_since = None
            return False, 0.0

        if difference <= REMOVE_DIFFERENCE_C:
            self._remove_candidate_since = self._remove_candidate_since or now
            elapsed = (now - self._remove_candidate_since).total_seconds()
            confidence = max(0.0, 1.0 - elapsed / REMOVE_CONFIRM.total_seconds())
            if now - self._remove_candidate_since >= REMOVE_CONFIRM:
                self._insert_candidate_since = None
                return False, 0.0
            return True, round(confidence, 2)

        self._remove_candidate_since = None
        confidence = min(1.0, max(0.0, difference / max(INSERT_DIFFERENCE_C, 0.1)))
        return True, round(confidence, 2)

    def _calculate_cook_state(
        self,
        *,
        now: datetime,
        inserted: bool,
        ambient: float,
        rate: float | None,
    ) -> tuple[str, str, float]:
        """Infer idle, inserted, heating, resting, cooling, or removed."""
        if not inserted:
            self._rest_candidate_since = None
            if self.data.inserted:
                return "removed", "tip and ambient converged after insertion", 0.8
            return "idle", "probe is not confirmed inserted", 1.0

        hot_environment = ambient >= COOK_AMBIENT_C
        rising = rate is not None and rate >= COOK_RATE_C_PER_MIN
        falling = rate is not None and rate <= COOLING_RATE_C_PER_MIN

        if hot_environment or rising:
            self._rest_candidate_since = None
            confidence_parts = [
                min(1.0, ambient / max(COOK_AMBIENT_C, 0.1)),
                min(1.0, max(rate or 0.0, 0.0) / max(COOK_RATE_C_PER_MIN, 0.01)),
            ]
            return "heating", "ambient is hot or tip is rising", round(max(confidence_parts), 2)

        if falling and ambient <= REST_AMBIENT_C and self.data.cooking:
            self._rest_candidate_since = self._rest_candidate_since or now
            elapsed = now - self._rest_candidate_since
            confidence = min(1.0, elapsed.total_seconds() / REST_CONFIRM.total_seconds())
            if elapsed >= REST_CONFIRM:
                return "resting", "tip is cooling outside a hot environment", 1.0
            return "cooling", "possible rest period is being confirmed", round(confidence, 2)

        if self.data.resting and falling:
            return "resting", "tip continues cooling during rest", 1.0

        if falling:
            return "cooling", "tip temperature is falling", 0.8

        self._rest_candidate_since = None
        return "inserted", "probe is inserted but active heating is not confirmed", 0.6

    def _calculate_rate(self) -> tuple[float | None, float, int]:
        """Calculate tip heating rate using rolling linear regression."""
        samples = list(self._samples)
        if len(samples) < 2:
            return None, 0.0, len(samples)

        span = samples[-1].timestamp - samples[0].timestamp
        if span < RATE_MIN_SPAN:
            confidence = min(0.5, span.total_seconds() / RATE_MIN_SPAN.total_seconds())
            return None, round(confidence, 2), len(samples)

        origin = samples[0].timestamp
        xs = [(sample.timestamp - origin).total_seconds() / 60.0 for sample in samples]
        ys = [sample.tip for sample in samples]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        if denominator <= 0:
            return None, 0.0, len(samples)

        slope = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(xs, ys, strict=True)
        ) / denominator

        predicted = [y_mean + slope * (x - x_mean) for x in xs]
        residual = sum(
            (y - estimate) ** 2
            for y, estimate in zip(ys, predicted, strict=True)
        )
        total = sum((y - y_mean) ** 2 for y in ys)
        r_squared = 1.0 if total <= 0.0001 else max(0.0, 1.0 - residual / total)
        span_factor = min(1.0, span.total_seconds() / SAMPLE_WINDOW.total_seconds())
        confidence = max(0.0, min(1.0, r_squared * span_factor))
        return round(slope, 3), round(confidence, 2), len(samples)

    def _calculate_notification_rate(self) -> float | None:
        """Return notifications per second over the current 30-second window."""
        if len(self._notification_times) < 2:
            return None
        span = (
            self._notification_times[-1] - self._notification_times[0]
        ).total_seconds()
        if span <= 0:
            return None
        return round((len(self._notification_times) - 1) / span, 2)

    def _update_session(
        self,
        *,
        now: datetime,
        cooking: bool,
        tip: float,
        ambient: float,
        rate: float | None,
    ) -> None:
        """Start, update, or finish an inferred cook session."""
        if cooking and self._active_session is None:
            self._active_session = CookSession(started_at=now.isoformat())
            self._active_session_rate_total = 0.0
            self._active_session_rate_samples = 0

        if self._active_session is None:
            return

        session = self._active_session
        session.sample_count += 1
        session.maximum_tip_temperature = max(
            session.maximum_tip_temperature or tip, tip
        )
        session.maximum_ambient_temperature = max(
            session.maximum_ambient_temperature or ambient, ambient
        )
        if rate is not None:
            self._active_session_rate_total += rate
            self._active_session_rate_samples += 1

        if not cooking and self.data.cooking:
            session.finished_at = now.isoformat()
            started = datetime.fromisoformat(session.started_at)
            session.duration_seconds = int((now - started).total_seconds())
            session.average_heating_rate = self._current_average_rate()
            self._history.append(session)
            self._history = self._history[-HISTORY_LIMIT:]
            self._active_session = None
            self._active_session_rate_total = 0.0
            self._active_session_rate_samples = 0
            self.hass.async_create_task(self._async_save_history())

    async def _async_save_history(self) -> None:
        """Persist completed cook sessions."""
        await self._store.async_save(
            {"history": [session.as_dict() for session in self._history]}
        )

    def _current_duration(self, now: datetime) -> int | None:
        """Return current inferred cook duration."""
        if self._active_session is None:
            return None
        started = datetime.fromisoformat(self._active_session.started_at)
        return int((now - started).total_seconds())

    def _current_average_rate(self) -> float | None:
        """Return average heating rate for the active cook."""
        if self._active_session_rate_samples == 0:
            return None
        return round(
            self._active_session_rate_total / self._active_session_rate_samples,
            3,
        )

    def _emit_event(self, event_type: str, data: MeaterData) -> None:
        """Notify event entities of an inferred transition."""
        data.last_cook_event = event_type
        payload = {
            "tip_temperature": data.tip_temperature,
            "ambient_temperature": data.ambient_temperature,
            "smoothed_tip_temperature": data.smoothed_tip_temperature,
            "smoothed_ambient_temperature": data.smoothed_ambient_temperature,
            "heating_rate": data.heating_rate,
            "cook_state": data.cook_state,
            "temperature_difference": data.temperature_difference,
            "rate_confidence": data.rate_confidence,
            "inserted_confidence": data.inserted_confidence,
            "cooking_confidence": data.cooking_confidence,
        }
        for listener in list(self._event_listeners):
            listener(event_type, payload)

    def _apply_adaptive_interval(self, data: MeaterData) -> None:
        """Select a fallback/watchdog interval."""
        if self._notifications_active:
            self.update_interval = NOTIFICATION_WATCHDOG_INTERVAL
            return
        self.update_interval = ACTIVE_POLL_INTERVAL if data.cooking else IDLE_POLL_INTERVAL

    async def _async_read_metadata(self) -> None:
        """Read optional Device Information Service values once."""
        assert self._client is not None
        metadata = {
            "manufacturer": MANUFACTURER_NAME_UUID,
            "model": MODEL_NUMBER_UUID,
            "serial_number": SERIAL_NUMBER_UUID,
            "firmware_version": FIRMWARE_REVISION_UUID,
            "hardware_version": HARDWARE_REVISION_UUID,
        }
        for attribute, uuid in metadata.items():
            value = await self._async_read_optional_text(uuid)
            if value:
                setattr(self.data, attribute, value)
        self.data.manufacturer = self.data.manufacturer or "Apption Labs"
        self.data.model = self.data.model or "MEATER"
        self._metadata_loaded = True

    async def _async_read_optional_text(self, uuid: str) -> str | None:
        """Read an optional UTF-8 characteristic."""
        assert self._client is not None
        try:
            payload = await asyncio.wait_for(
                self._client.read_gatt_char(uuid),
                timeout=CONNECTION_TIMEOUT,
            )
        except (BleakError, TimeoutError):
            return None
        value = bytes(payload).decode("utf-8", errors="replace").strip("\x00 \t\r\n")
        return value or None

    def _disconnected(self, _client: BleakClientWithServiceCache) -> None:
        """Handle an unexpected disconnection."""
        self._client = None
        self._notifications_active = False
        self.data.connected = False
        self.update_interval = DEFAULT_SCAN_INTERVAL
        self.hass.async_create_task(self.async_request_refresh())

    async def async_disconnect(self) -> None:
        """Disconnect from the probe and discard the client."""
        client = self._client
        self._client = None
        self._notifications_active = False
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except BleakError:
                _LOGGER.debug("Error disconnecting", exc_info=True)


def _u16_le(payload: bytes, offset: int) -> int:
    return int.from_bytes(payload[offset : offset + 2], byteorder="little")


def _decode_temperature(raw: int) -> float:
    return (raw + 8.0) / 16.0


def _decode_temperatures(payload: bytes) -> tuple[float, float]:
    if len(payload) < 6:
        raise UpdateFailed(
            f"Unexpected MEATER temperature payload length: {len(payload)}"
        )
    tip_raw = _u16_le(payload, 0)
    ra = _u16_le(payload, 2)
    oa = _u16_le(payload, 4)
    correction_base = ra - min(48, oa)
    correction = max(0, (correction_base * 16 * 589) // 1487)
    tip = _decode_temperature(tip_raw)
    ambient = _decode_temperature(tip_raw + correction)
    if not math.isfinite(tip) or not math.isfinite(ambient):
        raise UpdateFailed("MEATER returned invalid temperature data")
    return round(tip, 2), round(ambient, 2)


def _decode_battery(payload: bytes) -> int:
    if len(payload) < 2:
        raise UpdateFailed(
            f"Unexpected MEATER battery payload length: {len(payload)}"
        )
    return min(100, _u16_le(payload, 0) * 10)
