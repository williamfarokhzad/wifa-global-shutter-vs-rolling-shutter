import json
from fractions import Fraction
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from shutter import compare

ROOT = Path(__file__).resolve().parents[1]
BASE = dict(rows=801, line_interval_us=10, exposure_us=1000, speed_px_s=1200, first_row="top")


class ShutterTests(unittest.TestCase):
    def test_worked_values(self):
        result = compare(BASE)
        self.assertEqual(result, dict(rolling_row_span_ms=8.0, rolling_skew_px=9.6,
                                      global_skew_px=0.0, blur_px_both_modes=1.2))

    def test_single_row_does_not_span_one_line_interval(self):
        result = compare(dict(BASE, rows=1))
        self.assertEqual(result["rolling_row_span_ms"], 0)
        self.assertEqual(result["rolling_skew_px"], 0)
        self.assertEqual(result["blur_px_both_modes"], 1.2)

    def test_stationary_target_has_time_span_without_distortion(self):
        result = compare(dict(BASE, speed_px_s=0))
        self.assertEqual(result["rolling_row_span_ms"], 8)
        self.assertEqual(result["rolling_skew_px"], 0)
        self.assertEqual(result["blur_px_both_modes"], 0)

    def test_reversing_motion_or_scan_flips_only_skew(self):
        for changes, expected in [({"first_row": "bottom"}, -9.6),
                                  ({"speed_px_s": -1200}, -9.6),
                                  ({"speed_px_s": -1200, "first_row": "bottom"}, 9.6)]:
            with self.subTest(changes=changes):
                result = compare(BASE | changes)
                self.assertEqual(result["rolling_skew_px"], expected)
                self.assertEqual(result["blur_px_both_modes"], 1.2)

    def test_shorter_exposure_changes_blur_not_skew(self):
        result = compare(dict(BASE, exposure_us=250))
        self.assertEqual(result["rolling_skew_px"], 9.6)
        self.assertEqual(result["blur_px_both_modes"], .3)

    def test_against_sampled_row_exposure_endpoints(self):
        rng = random.Random(338)
        for _ in range(120):
            rows, interval, exposure, speed = (rng.randint(1, 200), rng.randint(1, 99),
                                               rng.randint(1, 5000), rng.randint(-2000, 2000))
            for direction in ("top", "bottom"):
                spans = []
                for row in range(rows):
                    ordinal = row if direction == "top" else rows - row - 1
                    start = Fraction(ordinal * interval, 10**6)
                    end = start + Fraction(exposure, 10**6)
                    spans.append((speed * start, speed * end))
                centroid = lambda pair: sum(pair) / 2
                result = compare(dict(rows=rows, line_interval_us=interval, exposure_us=exposure,
                                      speed_px_s=speed, first_row=direction))
                self.assertAlmostEqual(result["rolling_skew_px"], float(centroid(spans[-1]) - centroid(spans[0])))
                self.assertAlmostEqual(result["blur_px_both_modes"], float(abs(spans[0][1] - spans[0][0])))

    def test_invalid_inputs(self):
        for changes in (dict(rows=True), dict(rows=0), dict(rows=3.0), dict(exposure_us=0),
                        dict(line_interval_us=-1), dict(first_row="left"), dict(speed_px_s=float("nan")),
                        dict(speed_px_s=float("inf")), dict(speed_px_s="1200"), dict(extra=1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                compare(BASE | changes)
        with self.assertRaises(ValueError):
            compare({})

    def test_cli_examples(self):
        for name, values in {"conveyor": (8, 9.6, 0, 1.2), "short-exposure": (8, 9.6, 0, .3),
                             "reverse-scan": (8, -9.6, 0, 1.2), "short-roi": (2, 2.4, 0, 1.2)}.items():
            with self.subTest(name=name):
                run = subprocess.run([sys.executable, "shutter.py", f"examples/{name}.json"],
                                     cwd=ROOT, check=True, capture_output=True, text=True)
                self.assertEqual(tuple(float(line.split(": ")[1]) for line in run.stdout.splitlines()), values)

    def test_cli_rejects_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text(json.dumps(BASE)[:-1] + ', "rows": 2}', encoding="utf-8")
            run = subprocess.run([sys.executable, "shutter.py", str(path)],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("duplicate JSON key: rows", run.stderr)


if __name__ == "__main__":
    unittest.main()
