$(function() {
    function BME680ChamberTempViewModel(parameters) {
        var self = this;

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            // Only handle messages from our plugin
            if (plugin !== "bme680_chambertemp") return;

            // If the plugin sent temperature, humidity, voc
            if (data.hasOwnProperty("temperature")) {
                $("#bme680_temp_value").text(data.temperature.toFixed(2));
            }
            if (data.hasOwnProperty("humidity")) {
                $("#bme680_humidity_value").text(data.humidity.toFixed(2));
            }
            if (data.hasOwnProperty("voc")) {
                // BME680 gas reading is in ohms, can be quite large
                $("#bme680_voc_value").text(data.voc.toFixed(0));
            }
        };
    }

    // Register ViewModel
    OCTOPRINT_VIEWMODELS.push({
        construct: BME680ChamberTempViewModel,
        dependencies: [],
        // Bind to our custom tab container
        elements: ["#tab_bme680_chambertemp"]
    });
});

