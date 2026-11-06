"""Compare exposure blur and row timing skew in a constant-speed image model."""

import argparse
import json
import math
from pathlib import Path

FIELDS = {"rows", "line_interval_us", "exposure_us", "speed_px_s", "first_row"}


def compare(data):
    """Return signed bottom-minus-top skew and nonnegative blur in pixels."""
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError("expected exactly: " + ", ".join(sorted(FIELDS)))
    rows = data["rows"]
    if type(rows) is not int or not 1 <= rows <= 100_000:
        raise ValueError("rows must be an integer from 1 to 100000")
    direction = data["first_row"]
    if direction not in ("top", "bottom"):
        raise ValueError("first_row must be top or bottom")

    def number(key, low, high):
        value = data[key]
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(f"{key} must be a finite number from {low} to {high}")
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        return value

    line = number("line_interval_us", 0, 1_000_000)
    exposure = number("exposure_us", 0, 10_000_000)
    speed = number("speed_px_s", -1_000_000_000, 1_000_000_000)
    if line == 0 or exposure == 0:
        raise ValueError("line_interval_us and exposure_us must be positive")

    span = (rows - 1) * line
    signed_span = span if direction == "top" else -span
    blur = abs(speed) * exposure / 1_000_000
    skew = speed * signed_span / 1_000_000
    return {
        "rolling_row_span_ms": span / 1_000,
        "rolling_skew_px": skew if skew else 0.0,
        "global_skew_px": 0.0,
        "blur_px_both_modes": blur if blur else 0.0,
    }


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", type=Path, help="path to a JSON scenario")
    args = parser.parse_args()
    try:
        data = json.loads(args.example.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
        result = compare(data)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for label, value in result.items():
        print(f"{label}: {value:.9g}")


if __name__ == "__main__":
    main()
