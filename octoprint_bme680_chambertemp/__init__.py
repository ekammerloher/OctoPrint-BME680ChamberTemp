# octoprint_bme680_chambertemp/__init__.py

from .bme680_chambertemp import BME680ChamberTempPlugin

__plugin_name__ = "BME680 Chamber Temperature"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Reads BME680 sensor data (temp/humidity/VOC) over I2C and shows as chamber data."
__plugin_pythoncompat__ = ">=3,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = BME680ChamberTempPlugin()
    
    global __plugin_hooks__
    __plugin_hooks__ = __plugin_implementation__.get_hooks()

