from __future__ import annotations

import importlib
import logging
import threading
import time

import octoprint.plugin

from .core import (
    RETRY_INTERVAL,
    candidate_i2c_addresses,
    default_settings,
    isoformat_utc,
    normalize_i2c_address,
    sanitize_number,
    validate_bus,
    validate_poll_interval,
    validate_temperature_offset,
)

PLUGIN_VERSION = "0.2.0"
CHIP_ID_REGISTER = 0xD0


class BME680ChamberTempPlugin(
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
):
    def __init__(self):
        super().__init__()
        self._sensor = None
        self._active_address = None
        self._worker_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._sensor_lock = threading.Lock()
        self._sensor_thread = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._status = "stopped"
        self._last_error = None
        self._last_success_timestamp = None
        self._latest_reading = {
            "temperature": None,
            "humidity": None,
            "gas_resistance": None,
            "timestamp": None,
        }
        self._last_logged_issue = None
        self._last_logged_issue_time = 0.0

    def get_settings_defaults(self):
        return default_settings()

    def get_template_configs(self):
        return [
            {
                "type": "tab",
                "name": "BME680 Chamber",
                "template": "bme680_chambertemp_tab.jinja2",
                "div": "tab_bme680_chambertemp",
                "custom_bindings": True,
            },
            {
                "type": "settings",
                "name": "BME680 Chamber Temp",
                "template": "bme680_chambertemp_settings.jinja2",
                "custom_bindings": True,
            },
        ]

    def get_assets(self):
        return {
            "js": ["js/bme680_chambertemp.js"],
            "css": ["css/bme680_chambertemp.css"],
        }

    def get_api_commands(self):
        return {}

    def on_api_get(self, request):
        from flask import jsonify

        return jsonify(self._build_payload())

    def on_after_startup(self):
        self._apply_logging_verbosity()
        self._logger.info("Starting BME680 chamber worker")
        self._set_status("initializing")
        self._start_worker()

    def on_shutdown(self):
        self._logger.info("Stopping BME680 chamber worker")
        self._stop_worker()
        self._set_status("stopped")
        self._send_state_update()

    def on_settings_save(self, data):
        cleaned = self._sanitize_settings_payload(data)
        octoprint.plugin.SettingsPlugin.on_settings_save(self, cleaned)
        self._apply_logging_verbosity()
        self._logger.info(
            (
                "Updated settings: bus=%s address=%s poll_interval=%ss "
                "inject_temperature=%s show_tab=%s"
            ),
            self._settings.get_int(["i2c_bus"]),
            self._settings.get(["i2c_address"]),
            self._settings.get_float(["poll_interval"]),
            self._settings.get_boolean(["inject_temperature"]),
            self._settings.get_boolean(["show_tab"]),
        )
        self._reset_sensor("initializing")
        self._wake_event.set()

    def temperatures_received(self, comm, parsed_temps):
        if not self._settings.get_boolean(["inject_temperature"]):
            return parsed_temps

        with self._state_lock:
            temperature = self._latest_reading["temperature"]

        if temperature is None:
            return parsed_temps

        parsed_temps.update({"chamber": (temperature, None)})
        return parsed_temps

    def get_hooks(self):
        return {
            "octoprint.comm.protocol.temperatures.received": self.temperatures_received,
        }

    def _sanitize_settings_payload(self, data):
        cleaned = dict(data)
        cleaned["i2c_address"] = normalize_i2c_address(data.get("i2c_address"))
        cleaned["i2c_bus"] = validate_bus(data.get("i2c_bus", 1))
        cleaned["poll_interval"] = validate_poll_interval(data.get("poll_interval", 5))
        cleaned["temperature_offset"] = validate_temperature_offset(
            data.get("temperature_offset", 0.0)
        )

        verbosity = str(data.get("logging_verbosity", "normal")).strip().lower()
        cleaned["logging_verbosity"] = verbosity if verbosity == "debug" else "normal"
        cleaned["inject_temperature"] = bool(data.get("inject_temperature", True))
        cleaned["show_tab"] = bool(data.get("show_tab", True))
        return cleaned

    def _current_config(self):
        return {
            "i2c_address": normalize_i2c_address(self._settings.get(["i2c_address"])),
            "i2c_bus": validate_bus(self._settings.get_int(["i2c_bus"])),
            "poll_interval": validate_poll_interval(self._settings.get_float(["poll_interval"])),
            "temperature_offset": validate_temperature_offset(
                self._settings.get_float(["temperature_offset"])
            ),
            "inject_temperature": self._settings.get_boolean(["inject_temperature"]),
            "show_tab": self._settings.get_boolean(["show_tab"]),
            "logging_verbosity": self._settings.get(["logging_verbosity"]),
        }

    def _build_payload(self):
        config = self._current_config()
        with self._state_lock:
            reading = dict(self._latest_reading)
            status = self._status
            last_error = self._last_error
            last_success_timestamp = self._last_success_timestamp
        return {
            "status": status,
            "last_error": last_error,
            "last_success_timestamp": last_success_timestamp,
            "last_success_iso": isoformat_utc(last_success_timestamp),
            "temperature": reading["temperature"],
            "humidity": reading["humidity"],
            "gas_resistance": reading["gas_resistance"],
            "reading_timestamp": reading["timestamp"],
            "reading_timestamp_iso": isoformat_utc(reading["timestamp"]),
            "configured_bus": config["i2c_bus"],
            "configured_address": config["i2c_address"],
            "active_address": None
            if self._active_address is None
            else f"0x{self._active_address:02X}",
            "inject_temperature": config["inject_temperature"],
            "show_tab": config["show_tab"],
            "plugin_version": PLUGIN_VERSION,
            "library_version": self._library_version(),
        }

    def _send_state_update(self):
        if not hasattr(self, "_plugin_manager") or self._plugin_manager is None:
            return
        self._plugin_manager.send_plugin_message(self._identifier, self._build_payload())

    def _start_worker(self):
        with self._worker_lock:
            if self._sensor_thread is not None and self._sensor_thread.is_alive():
                return

            self._stop_event.clear()
            self._wake_event.clear()
            self._sensor_thread = threading.Thread(
                target=self._worker_loop,
                name="BME680ChamberTempWorker",
                daemon=True,
            )
            self._sensor_thread.start()

    def _stop_worker(self):
        self._stop_event.set()
        self._wake_event.set()
        thread = self._sensor_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)

    def _worker_loop(self):
        self._send_state_update()
        while not self._stop_event.is_set():
            config = self._current_config()

            if self._sensor is None and not self._initialize_sensor(config):
                if self._wait(RETRY_INTERVAL):
                    break
                continue

            try:
                self._perform_read(config)
                self._set_status("connected")
            except Exception as exc:  # pragma: no cover - exercised via tests with fake sensor
                self._handle_read_error(exc)

            if self._wait(config["poll_interval"]):
                break

    def _wait(self, timeout):
        if self._stop_event.is_set():
            return True
        if self._wake_event.wait(timeout):
            self._wake_event.clear()
        return self._stop_event.is_set()

    def _initialize_sensor(self, config):
        bus_number = config["i2c_bus"]
        addresses = candidate_i2c_addresses(config["i2c_address"])
        last_error = None
        self._set_status("initializing")

        for address in addresses:
            try:
                self._logger.info(
                    "Initializing BME680 on I2C bus %s at address 0x%02X",
                    bus_number,
                    address,
                )
                sensor = self._create_sensor(bus_number, address)
                with self._sensor_lock:
                    self._sensor = sensor
                    self._active_address = address
                self._logger.info(
                    "Initialized BME680 on I2C bus %s at address 0x%02X",
                    bus_number,
                    address,
                )
                self._send_state_update()
                return True
            except Exception as exc:
                last_error = exc
                self._log_worker_issue(
                    f"Sensor initialization failed on bus {bus_number} address 0x{address:02X}",
                    exc,
                )

        self._clear_current_reading()
        self._set_status("disconnected", self._format_error_message(last_error))
        self._send_state_update()
        return False

    def _create_sensor(self, bus_number, address):
        bus_module = importlib.import_module("adafruit_extended_bus")
        device_module = importlib.import_module("adafruit_bus_device.i2c_device")
        driver_module = importlib.import_module("adafruit_bme680")

        self._logger.info("Configured I2C bus: %s", bus_number)
        self._logger.info("Configured I2C address: 0x%02X", address)

        i2c = bus_module.ExtendedI2C(bus_number)
        chip_id = self._read_chip_id(device_module, i2c, address)
        if chip_id is None:
            self._logger.info("Detected chip ID at 0x%02X: unavailable", address)
        else:
            self._logger.info("Detected chip ID at 0x%02X: 0x%02X", address, chip_id)

        sensor = driver_module.Adafruit_BME680_I2C(i2c, address=address)
        sensor.sea_level_pressure = 1013.25
        return sensor

    def _read_chip_id(self, device_module, i2c, address):
        try:
            with device_module.I2CDevice(i2c, address) as device:
                device.write(bytes([CHIP_ID_REGISTER]))
                result = bytearray(1)
                device.readinto(result)
                return result[0]
        except Exception:
            return None

    def _perform_read(self, config):
        with self._sensor_lock:
            sensor = self._sensor
        if sensor is None:
            raise RuntimeError("Sensor is not initialized")

        temperature = sanitize_number(sensor.temperature)
        humidity = sanitize_number(sensor.relative_humidity)
        gas_resistance = sanitize_number(sensor.gas)

        if temperature is None or humidity is None or gas_resistance is None:
            raise RuntimeError("Sensor returned invalid reading")

        temperature += config["temperature_offset"]
        now = time.time()

        with self._state_lock:
            self._latest_reading = {
                "temperature": temperature,
                "humidity": humidity,
                "gas_resistance": gas_resistance,
                "timestamp": now,
            }
            self._last_success_timestamp = now
            self._last_error = None
            self._status = "connected"

        self._send_state_update()

    def _handle_read_error(self, exc):
        self._log_worker_issue("Sensor read failed", exc)
        with self._sensor_lock:
            self._sensor = None
            self._active_address = None
        self._clear_current_reading()
        self._set_status("read_error", self._format_error_message(exc))
        self._send_state_update()

    def _clear_current_reading(self):
        with self._state_lock:
            self._latest_reading = {
                "temperature": None,
                "humidity": None,
                "gas_resistance": None,
                "timestamp": None,
            }

    def _reset_sensor(self, status):
        with self._sensor_lock:
            self._sensor = None
            self._active_address = None
        self._clear_current_reading()
        self._set_status(status)
        self._send_state_update()

    def _set_status(self, status, last_error=None):
        with self._state_lock:
            self._status = status
            if last_error is not None or status in {
                "connected",
                "initializing",
                "stopped",
            }:
                self._last_error = last_error

    def _format_error_message(self, exc):
        if exc is None:
            return None
        return f"{type(exc).__name__}: {exc}"

    def _log_worker_issue(self, prefix, exc):
        signature = f"{prefix}|{type(exc).__name__}|{exc}"
        now = time.monotonic()
        if signature != self._last_logged_issue or now - self._last_logged_issue_time >= 60:
            self._logger.warning("%s: %s", prefix, self._format_error_message(exc))
            self._last_logged_issue = signature
            self._last_logged_issue_time = now

    def _apply_logging_verbosity(self):
        level = (
            logging.DEBUG if self._settings.get(["logging_verbosity"]) == "debug" else logging.INFO
        )
        self._logger.setLevel(level)

    def _library_version(self):
        try:
            driver_module = importlib.import_module("adafruit_bme680")
        except Exception:
            return None
        return getattr(driver_module, "__version__", None)
