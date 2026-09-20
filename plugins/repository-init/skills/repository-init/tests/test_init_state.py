from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "init_state.py"
SPEC = importlib.util.spec_from_file_location("repository_init_state", SCRIPT)
assert SPEC and SPEC.loader
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class InitStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_governance(self, *, license_name: str = "LICENSE") -> None:
        (self.root / license_name).write_text("MIT License\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("ongoing rules\n", encoding="utf-8")
        (self.root / "SECURITY.md").write_text("security policy\n", encoding="utf-8")

    def test_missing_is_read_only(self) -> None:
        before = sorted(self.root.iterdir())
        self.assertEqual({"status": "missing"}, state.inspect(self.root))
        self.assertEqual(before, sorted(self.root.iterdir()))

    def test_begin_records_decision_and_resume_preserves_it(self) -> None:
        first = state.begin(self.root, "MIT", "mit")
        marker = self.root / state.MARKER
        marker_bytes = marker.read_bytes()
        self.assertEqual({"schema_version": 1, "status": "in_progress", "license": "MIT", "language_profile": "mit"}, first)
        self.assertEqual(first, state.begin(self.root, "MIT", "mit"))
        self.assertEqual(marker_bytes, marker.read_bytes())
        with self.assertRaises(state.StateError):
            state.begin(self.root, "Apache-2.0", "non-mit")
        self.assertEqual(marker_bytes, marker.read_bytes())

    def test_non_mit_profile_can_be_saved(self) -> None:
        self.assertEqual("non-mit", state.begin(self.root, "Apache-2.0", "non-mit")["language_profile"])

    def test_complete_requires_governance_files_and_alternate_license(self) -> None:
        state.begin(self.root, "MIT", "mit")
        with self.assertRaises(state.StateError):
            state.complete(self.root)
        self.write_governance(license_name="LICENSE.md")
        self.assertEqual("complete", state.complete(self.root)["status"])

    def test_complete_and_repeat_are_byte_and_timestamp_stable(self) -> None:
        self.write_governance()
        state.begin(self.root, "MIT", "mit")
        marker = self.root / state.MARKER
        state.complete(self.root)
        marker_bytes = marker.read_bytes()
        marker_stat = marker.stat()
        files = {path: path.read_bytes() for path in self.root.iterdir()}
        self.assertEqual(state.inspect(self.root), state.complete(self.root))
        self.assertEqual(marker_bytes, marker.read_bytes())
        self.assertEqual(marker_stat.st_mtime_ns, marker.stat().st_mtime_ns)
        self.assertEqual(files, {path: path.read_bytes() for path in self.root.iterdir()})
        self.assertEqual(state.complete(self.root), state.begin(self.root, "Apache-2.0", "non-mit"))

    def test_invalid_marker_is_fail_closed(self) -> None:
        marker = self.root / state.MARKER
        marker.write_text(json.dumps({"schema_version": 1, "status": "complete", "license": "MIT"}), encoding="utf-8")
        before = marker.read_bytes()
        with self.assertRaises(state.StateError):
            state.inspect(self.root)
        self.assertEqual(before, marker.read_bytes())

    def test_unknown_schema_is_fail_closed(self) -> None:
        marker = self.root / state.MARKER
        marker.write_text(json.dumps({"schema_version": 2, "status": "complete", "license": "MIT", "language_profile": "mit"}), encoding="utf-8")
        with self.assertRaises(state.StateError):
            state.inspect(self.root)

    def test_existing_lock_blocks_writes_and_is_preserved(self) -> None:
        lock = self.root / state.LOCK
        lock.write_text("external operation\n", encoding="utf-8")
        with self.assertRaises(state.StateError):
            state.begin(self.root, "MIT", "mit")
        self.assertTrue(lock.is_file())
        self.assertFalse((self.root / state.MARKER).exists())

    def test_failed_atomic_replace_does_not_leave_temporary_marker(self) -> None:
        with mock.patch.object(state.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                state.begin(self.root, "MIT", "mit")
        self.assertFalse((self.root / state.MARKER).exists())
        self.assertEqual([], list(self.root.glob(".repository-init-*.tmp")))

    @unittest.skipUnless(hasattr(__import__("os"), "symlink"), "symbolic links are unavailable")
    def test_symlink_marker_is_rejected(self) -> None:
        target = self.root / "real-marker"
        target.write_text("{}", encoding="utf-8")
        marker = self.root / state.MARKER
        try:
            marker.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaises(state.StateError):
            state.inspect(self.root)


if __name__ == "__main__":
    unittest.main()
