from .bme680_chambertemp import PLUGIN_VERSION, BME680ChamberTempPlugin

__plugin_name__ = "BME680 Chamber Temperature"
__plugin_version__ = PLUGIN_VERSION
__plugin_description__ = (
    "Read BME680 environmental data over I2C and publish chamber temperature in OctoPrint."
)
__plugin_pythoncompat__ = ">=3.8,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = BME680ChamberTempPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = __plugin_implementation__.get_hooks()
