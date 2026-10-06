"""Fast, offline checks for the renderer's input-validation boundaries."""

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_video import interval, unique
from video_common import keys, local, number


class ValidationTests(unittest.TestCase):
    def test_finite_nonnegative_numbers(self):
        for value in (0, 0.25, 7):
            with self.subTest(value=value):
                self.assertEqual(number(value, "time"), value)

    def test_invalid_numbers_are_rejected(self):
        for value in (True, False, None, "1", -1, math.nan, math.inf, -math.inf, 10 ** 1000):
            with self.subTest(value=repr(value)[:40]):
                with self.assertRaises(ValueError):
                    number(value, "time")

    def test_strict_keys(self):
        keys({"version": 1, "clips": [], "overlays": []}, ("version", "clips"), ("overlays",))
        for data in ({"version": 1}, {"version": 1, "clips": [], "surprise": True}, []):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    keys(data, ("version", "clips"))

    def test_duplicate_json_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            json.loads('{"version": 1, "version": 2}', object_pairs_hook=unique)

    def test_valid_interval(self):
        self.assertEqual(interval({"start": 0.25, "end": 1}, 1), (0.25, 1))

    def test_invalid_intervals(self):
        for start, end in ((0, 0), (1, 0.5), (0, 2), (-1, 1), (True, 1), (0, math.nan)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    interval({"start": start, "end": end}, 1)

    def test_reject_remote_and_control_character_paths(self):
        for value in ("https://example.com/video.mp4", "file:///tmp/video.mp4", "clip\n.mp4", "", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    local(value, Path.cwd())

    def test_local_path_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            source = base / "clip with spaces.mp4"
            source.write_bytes(b"synthetic path-test fixture")
            self.assertEqual(local(source.name, base), source)
            self.assertEqual(local("new.mp4", base, existing=False), base / "new.mp4")
            with self.assertRaisesRegex(ValueError, "Refusing overwrite"):
                local(source.name, base, existing=False)
            with self.assertRaisesRegex(ValueError, "Not a regular file"):
                local(str(base), base)
            with self.assertRaisesRegex(ValueError, "Output parent"):
                local("missing/output.mp4", base, existing=False)
            with self.assertRaises(OSError):
                local("missing.mp4", base)

    def test_dangling_output_symlink_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            link = base / "output.mp4"
            link.symlink_to(base / "missing-target.mp4")
            with self.assertRaisesRegex(ValueError, "Refusing overwrite"):
                local(link.name, base, existing=False)


if __name__ == "__main__":
    unittest.main()
