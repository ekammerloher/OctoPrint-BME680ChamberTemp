$(function () {
    function BME680ChamberTempViewModel(parameters) {
        var self = this;

        self.status = ko.observable("initializing");
        self.temperature = ko.observable(null);
        self.humidity = ko.observable(null);
        self.gasResistance = ko.observable(null);
        self.lastUpdate = ko.observable(null);
        self.lastSuccess = ko.observable(null);
        self.lastError = ko.observable(null);
        self.configuredBus = ko.observable(null);
        self.configuredAddress = ko.observable(null);
        self.activeAddress = ko.observable(null);
        self.temperatureName = ko.observable("chamber");
        self.pluginVersion = ko.observable(null);
        self.libraryVersion = ko.observable(null);
        self.showTab = ko.observable(true);
        self.refreshTimer = null;

        self.formatNumber = function (value, digits) {
            return _.isNumber(value) && _.isFinite(value) ? value.toFixed(digits) : "--";
        };

        self.temperatureText = ko.pureComputed(function () {
            return self.formatNumber(self.temperature(), 2);
        });

        self.humidityText = ko.pureComputed(function () {
            return self.formatNumber(self.humidity(), 2);
        });

        self.gasResistanceText = ko.pureComputed(function () {
            return _.isNumber(self.gasResistance()) && _.isFinite(self.gasResistance())
                ? Math.round(self.gasResistance()).toString()
                : "--";
        });

        self.statusText = ko.pureComputed(function () {
            var status = self.status();
            if (status === "connected") return "Connected";
            if (status === "initializing") return "Initializing";
            if (status === "read_error") return "Read error";
            if (status === "disconnected") return "Disconnected";
            if (status === "stopped") return "Stopped";
            return "Unknown";
        });

        self.renderFallbackState = function () {
            $("#bme680_chambertemp_status, #bme680_chambertemp_settings_status").text(self.statusText());
            $("#bme680_chambertemp_temperature").text(self.temperatureText());
            $("#bme680_chambertemp_humidity").text(self.humidityText());
            $("#bme680_chambertemp_gas").text(self.gasResistanceText());
            $("#bme680_chambertemp_last_update").text(self.lastUpdateText());
            $("#bme680_chambertemp_last_success, #bme680_chambertemp_settings_last_success").text(self.lastSuccessText());
            $("#bme680_chambertemp_last_error, #bme680_chambertemp_settings_last_error").text(self.lastErrorText());
            $("#bme680_chambertemp_configured_bus, #bme680_chambertemp_settings_configured_bus").text(self.configuredBus() == null ? "--" : self.configuredBus());
            $("#bme680_chambertemp_configured_address, #bme680_chambertemp_settings_configured_address").text(self.configuredAddress() || "--");
            $("#bme680_chambertemp_active_address, #bme680_chambertemp_settings_active_address").text(self.activeAddress() || "--");
            $("#bme680_chambertemp_plugin_version, #bme680_chambertemp_settings_plugin_version").text(self.pluginVersion() || "--");
            $("#bme680_chambertemp_library_version, #bme680_chambertemp_settings_library_version").text(self.libraryVersion() || "--");
            $("#bme680_chambertemp_settings_temperature_name").text(self.temperatureName() || "chamber");
        };

        self.isReadingAvailable = ko.pureComputed(function () {
            return _.isNumber(self.temperature()) && _.isFinite(self.temperature());
        });

        self.lastUpdateText = ko.pureComputed(function () {
            return self.lastUpdate() || "--";
        });

        self.lastSuccessText = ko.pureComputed(function () {
            return self.lastSuccess() || "--";
        });

        self.lastErrorText = ko.pureComputed(function () {
            return self.lastError() || "--";
        });

        self.updateState = function (data) {
            if (!data) return;

            self.status(data.status || "unknown");
            self.temperature(_.isNumber(data.temperature) && _.isFinite(data.temperature) ? data.temperature : null);
            self.humidity(_.isNumber(data.humidity) && _.isFinite(data.humidity) ? data.humidity : null);
            self.gasResistance(_.isNumber(data.gas_resistance) && _.isFinite(data.gas_resistance) ? data.gas_resistance : null);
            self.lastUpdate(data.reading_timestamp_iso || null);
            self.lastSuccess(data.last_success_iso || null);
            self.lastError(data.last_error || null);
            self.configuredBus(data.configured_bus);
            self.configuredAddress(data.configured_address || "--");
            self.activeAddress(data.active_address || "--");
            self.temperatureName(data.temperature_name || "chamber");
            self.pluginVersion(data.plugin_version || "--");
            self.libraryVersion(data.library_version || "--");
            self.showTab(data.show_tab !== false);
            self.toggleTabVisibility();
            self.renderFallbackState();
        };

        self.toggleTabVisibility = function () {
            var tabLink = $("a[href='#tab_bme680_chambertemp']").closest("li");
            tabLink.toggle(self.showTab());
        };

        self.requestState = function () {
            return OctoPrint.simpleApiGet("bme680_chambertemp")
                .done(function (response) {
                    self.updateState(response);
                })
                .fail(function () {
                    // Ignore transient auth/socket timing issues; polling will retry.
                });
        };

        self.startPolling = function () {
            if (self.refreshTimer !== null) return;
            self.refreshTimer = window.setInterval(function () {
                self.requestState();
            }, 10000);
        };

        self.stopPolling = function () {
            if (self.refreshTimer === null) return;
            window.clearInterval(self.refreshTimer);
            self.refreshTimer = null;
        };

        self.onBeforeBinding = function () {
            self.requestState();
            self.startPolling();
        };

        self.onSettingsShown = function () {
            self.requestState();
        };

        self.onUserLoggedIn = function () {
            self.requestState();
        };

        self.onUserLoggedOut = function () {
            self.stopPolling();
        };

        self.onAllBound = function () {
            self.startPolling();
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "bme680_chambertemp") return;
            self.updateState(data);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: BME680ChamberTempViewModel,
        dependencies: [],
        elements: ["#tab_bme680_chambertemp"]
    });
});
