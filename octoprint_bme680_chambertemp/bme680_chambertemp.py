import octoprint.plugin
import threading
import time

import board
import busio
import adafruit_bme680

class BME680ChamberTempPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.ShutdownPlugin
):
    def __init__(self):
        super().__init__()
        self._sensor_thread = None
        self._stop_thread = False

        # We'll store the latest readings here
        self._current_temperature = None
        self._current_humidity = None
        self._current_voc_resistance = None

        self.bme680 = None

    def on_after_startup(self):
        self._logger.info("BME680ChamberTempPlugin: Attempting sensor initialization...")
        try:
            self._init_sensor_with_retries()
            if self.bme680:
                self._logger.info("BME680ChamberTempPlugin: Sensor initialized successfully.")
                # Start background thread to read the sensor
                self._stop_thread = False
                self._sensor_thread = threading.Thread(target=self.read_sensor_loop)
                self._sensor_thread.daemon = True
                self._sensor_thread.start()
            else:
                self._logger.error("BME680ChamberTempPlugin: Could not initialize sensor after retries.")
        except Exception as e:
            self._logger.error(f"BME680ChamberTempPlugin: Failed to init sensor: {e}")

    def _init_sensor_with_retries(self, max_attempts=5, delay=2):
        """
        Tries to create the BME680 object, checking addresses 0x76 & 0x77
        up to `max_attempts` times with `delay` seconds in between.
        """
        i2c = busio.I2C(board.SCL, board.SDA)
        possible_addresses = [0x76, 0x77]

        for attempt in range(1, max_attempts + 1):
            for addr in possible_addresses:
                try:
                    self._logger.info(f"Attempt {attempt}, trying I2C address 0x{addr:02X} ...")
                    sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=addr)
                    # If creation succeeds, set defaults
                    sensor.sea_level_pressure = 1013.25
                    self.bme680 = sensor
                    return  # Stop on first success
                except Exception as ex:
                    self._logger.warning(
                        f"Attempt {attempt} for addr 0x{addr:02X} failed: {ex}"
                    )
            # If neither address worked this attempt, wait, then try again
            time.sleep(delay)

    def read_sensor_loop(self):
        while not self._stop_thread:
            try:
                if self.bme680 is not None:
                    # Gather readings
                    self._current_temperature = self.bme680.temperature  # °C
                    self._current_humidity = self.bme680.relative_humidity  # %
                    self._current_voc_resistance = self.bme680.gas  # ohms

                    # Send data to front-end
                    self._plugin_manager.send_plugin_message(
                        self._identifier,
                        {
                            "temperature": self._current_temperature,
                            "humidity": self._current_humidity,
                            "voc": self._current_voc_resistance,
                        }
                    )
            except Exception as e:
                self._logger.error(f"BME680ChamberTempPlugin: Error reading sensor: {e}")

            time.sleep(5)  # Adjust your polling interval as desired

    def on_shutdown(self):
        # Cleanly stop the sensor thread
        self._stop_thread = True
        if self._sensor_thread and self._sensor_thread.is_alive():
            self._sensor_thread.join()

    #
    #  ----- Integrating into the default temperature graph -----
    #
    def temperatures_received(self, comm, parsed_temps):
        if self._current_temperature is not None:
            parsed_temps.update({"chamber": (self._current_temperature, None)})
        return parsed_temps

    def get_hooks(self):
        return {
            "octoprint.comm.protocol.temperatures.received": self.temperatures_received
        }

    #
    #  ----- TemplatePlugin / AssetPlugin definitions -----
    #
    def get_template_configs(self):
        return [
            {
                "type": "tab",
                "name": "BME680 Env. Data",
                "template": "bme680_chambertemp_tab.jinja2",
                "div": "tab_bme680_chambertemp",
            }
        ]

    def get_assets(self):
        return {
            "js": ["js/bme680_chambertemp.js"],
        }
