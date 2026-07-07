# setup.py
import os
from setuptools import setup

# These plugin variables can be adjusted as needed:
plugin_identifier = "bme680_chambertemp"
plugin_package = "octoprint_bme680_chambertemp"
plugin_name = "OctoPrint-BME680ChamberTemp"
plugin_version = "0.1.0"
plugin_description = "Reads BME680 sensor data (temp/humidity/VOC) over I2C and injects chamber temperature into OctoPrint."
plugin_author = "Eugen Kammerloher"
plugin_author_email = "eugen.kammerloher@gmail.com"
plugin_url = "https://github.com/yourusername/OctoPrint-BME680ChamberTemp"
plugin_license = "MIT"

# Any Python dependencies your plugin needs
plugin_requires = [
    "adafruit-circuitpython-bme680"
]

# Additional package data to include
# We'll tell setuptools to include files in "static/" and "templates/".
# This works in conjunction with include_package_data=True below.
package_data = {
    plugin_package: [
        "static/js/*.js",
        "static/css/*.css",
        "templates/*.jinja2",
        # Add more globs or file patterns if needed
    ]
}

setup(
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    author_email=plugin_author_email,
    url=plugin_url,
    license=plugin_license,

    # The main plugin package
    packages=[plugin_package],
    include_package_data=True,  # IMPORTANT: includes non-.py files specified in package_data or MANIFEST.in
    package_data=package_data,

    # Plugin dependencies
    install_requires=plugin_requires,

    # This registers your plugin with OctoPrint under the "octoprint.plugin" entry point
    entry_points={
        "octoprint.plugin": [
            f"{plugin_identifier} = {plugin_package}"
        ]
    },

    # If you have a README file, you can include it here:
    long_description=open(os.path.join(os.path.dirname(__file__), "README.md")).read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
)

