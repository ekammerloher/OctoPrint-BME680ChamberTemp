from __future__ import annotations

import sys
import types


def _install_octoprint_stub():
    if "octoprint.plugin" in sys.modules:
        return

    octoprint_module = types.ModuleType("octoprint")
    plugin_module = types.ModuleType("octoprint.plugin")

    for name in [
        "AssetPlugin",
        "SettingsPlugin",
        "ShutdownPlugin",
        "SimpleApiPlugin",
        "StartupPlugin",
        "TemplatePlugin",
    ]:
        setattr(plugin_module, name, type(name, (), {}))

    octoprint_module.plugin = plugin_module
    sys.modules["octoprint"] = octoprint_module
    sys.modules["octoprint.plugin"] = plugin_module


_install_octoprint_stub()
