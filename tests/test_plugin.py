from __future__ import annotations

import logging
import threading
import time
from contextlib import suppress

from octoprint_bme680_chambertemp.bme680_chambertemp import BME680ChamberTempPlugin


class FakeSettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, path):
        return self._data[path[0]]

    def get_int(self, path):
        return int(self._data[path[0]])

    def get_float(self, path):
        return float(self._data[path[0]])

    def get_boolean(self, path):
        return bool(self._data[path[0]])


class FakePluginManager:
    def __init__(self):
        self.messages = []

    def send_plugin_message(self, identifier, payload):
        self.messages.append((identifier, payload))


class SensorSequence:
    def __init__(self, readings=None, error=None):
        self._readings = readings or [(25.0, 40.0, 12345.0)]
        self._error = error
        self._index = 0

    @property
    def temperature(self):
        if self._error:
            raise self._error
        return self._readings[self._index][0]

    @property
    def relative_humidity(self):
        return self._readings[self._index][1]

    @property
    def gas(self):
        value = self._readings[self._index][2]
        self._index = min(self._index + 1, len(self._readings) - 1)
        return value


def make_plugin(settings=None):
    plugin = BME680ChamberTempPlugin()
    plugin._identifier = "bme680_chambertemp"
    plugin._settings = FakeSettings(settings or plugin.get_settings_defaults())
    plugin._plugin_manager = FakePluginManager()
    plugin._logger = logging.getLogger(f"test-{time.time()}")
    plugin._logger.addHandler(logging.NullHandler())
    return plugin


def test_sensor_unavailable_at_startup():
    plugin = make_plugin()
    plugin._create_sensor = lambda bus, address: (_ for _ in ()).throw(OSError("missing"))

    assert plugin._initialize_sensor(plugin._current_config()) is False
    payload = plugin._build_payload()
    assert payload["status"] == "disconnected"
    assert payload["temperature"] is None


def test_successful_reading_and_offset():
    plugin = make_plugin({**make_plugin().get_settings_defaults(), "temperature_offset": 1.5})
    plugin._sensor = SensorSequence(readings=[(25.0, 41.2, 10001.0)])

    plugin._perform_read(plugin._current_config())
    payload = plugin._build_payload()
    assert payload["temperature"] == 26.5
    assert payload["humidity"] == 41.2
    assert payload["gas_resistance"] == 10001.0
    assert payload["last_success_timestamp"] is not None


def test_read_failure_after_success_clears_current_reading():
    plugin = make_plugin()
    plugin._sensor = SensorSequence(readings=[(25.0, 40.0, 12345.0)])
    plugin._perform_read(plugin._current_config())

    plugin._sensor = SensorSequence(error=RuntimeError("boom"))
    plugin._handle_read_error(RuntimeError("boom"))

    payload = plugin._build_payload()
    assert payload["status"] == "read_error"
    assert payload["temperature"] is None
    assert payload["last_success_timestamp"] is not None


def test_no_temperature_injection_when_disabled():
    plugin = make_plugin({**make_plugin().get_settings_defaults(), "inject_temperature": False})
    plugin._sensor = SensorSequence(readings=[(24.0, 40.0, 12000.0)])
    plugin._perform_read(plugin._current_config())

    parsed = plugin.temperatures_received(None, {})
    assert parsed == {}


def test_no_temperature_injection_without_valid_reading():
    plugin = make_plugin()
    parsed = plugin.temperatures_received(None, {})
    assert parsed == {}


def test_message_payload_handles_missing_invalid_readings():
    plugin = make_plugin()
    plugin._sensor = SensorSequence(readings=[(float("nan"), 40.0, 1.0)])

    with suppress(RuntimeError):
        plugin._perform_read(plugin._current_config())

    payload = plugin._build_payload()
    assert payload["temperature"] is None
    assert payload["humidity"] is None
    assert payload["gas_resistance"] is None


def test_clean_worker_shutdown():
    plugin = make_plugin()
    started = threading.Event()

    def worker():
        started.set()
        plugin._stop_event.wait(1)

    plugin._sensor_thread = threading.Thread(target=worker)
    plugin._sensor_thread.start()
    assert started.wait(0.2)

    plugin._stop_worker()
    assert not plugin._sensor_thread.is_alive()
