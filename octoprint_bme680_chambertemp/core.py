from __future__ import annotations

import math
from datetime import datetime, timezone

DEFAULT_I2C_ADDRESS = "0x76"
AUTO_I2C_ADDRESS = "auto"
MIN_POLL_INTERVAL = 1.0
RETRY_INTERVAL = 10.0
DEFAULT_POLL_INTERVAL = 5.0


def normalize_i2c_address(value):
    if value is None:
        return DEFAULT_I2C_ADDRESS

    if isinstance(value, str):
        cleaned = value.strip().lower()
        if not cleaned:
            return DEFAULT_I2C_ADDRESS
        if cleaned == AUTO_I2C_ADDRESS:
            return AUTO_I2C_ADDRESS
        try:
            parsed = int(cleaned, 0)
        except ValueError as exc:
            raise ValueError("I2C address must be 'auto', hex, or decimal") from exc
    elif isinstance(value, int):
        parsed = value
    else:
        raise ValueError("Unsupported I2C address type")

    if parsed < 0x03 or parsed > 0x77:
        raise ValueError("I2C address must be between 0x03 and 0x77")

    return f"0x{parsed:02x}"


def candidate_i2c_addresses(value):
    normalized = normalize_i2c_address(value)
    if normalized == AUTO_I2C_ADDRESS:
        return [0x76, 0x77]
    return [int(normalized, 16)]


def validate_poll_interval(value):
    try:
        interval = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Polling interval must be numeric") from exc

    if interval < MIN_POLL_INTERVAL:
        return MIN_POLL_INTERVAL
    return interval


def validate_bus(value):
    try:
        bus = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("I2C bus must be an integer") from exc

    if bus < 0:
        raise ValueError("I2C bus must be zero or greater")
    return bus


def validate_temperature_offset(value):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Temperature offset must be numeric") from exc


def sanitize_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None
    return number


def isoformat_utc(timestamp):
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def default_settings():
    return {
        "i2c_address": DEFAULT_I2C_ADDRESS,
        "i2c_bus": 1,
        "poll_interval": DEFAULT_POLL_INTERVAL,
        "temperature_offset": 0.0,
        "inject_temperature": True,
        "show_tab": True,
        "logging_verbosity": "normal",
    }
