from octoprint_bme680_chambertemp.core import (
    candidate_i2c_addresses,
    default_settings,
    normalize_i2c_address,
    sanitize_number,
    validate_poll_interval,
    validate_temperature_name,
)


def test_default_settings():
    defaults = default_settings()
    assert defaults["i2c_address"] == "0x76"
    assert defaults["i2c_bus"] == 1
    assert defaults["poll_interval"] == 5.0
    assert defaults["inject_temperature"] is True
    assert defaults["show_tab"] is True


def test_normalize_i2c_address():
    assert normalize_i2c_address("0x76") == "0x76"
    assert normalize_i2c_address("118") == "0x76"
    assert normalize_i2c_address("auto") == "auto"
    assert candidate_i2c_addresses("auto") == [0x76, 0x77]


def test_invalid_i2c_address_raises():
    try:
        normalize_i2c_address("0x80")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid I2C address to raise")


def test_poll_interval_clamps_to_minimum():
    assert validate_poll_interval(0.2) == 1.0


def test_sanitize_number_rejects_invalid_values():
    assert sanitize_number(float("nan")) is None
    assert sanitize_number("not-a-number") is None
    assert sanitize_number(1.25) == 1.25


def test_temperature_name_defaults_when_blank():
    assert validate_temperature_name("") == "chamber"
    assert validate_temperature_name(" enclosure ") == "enclosure"
