from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from registry_metadata import MetadataError, normalize  # noqa: E402
from release_policy import evaluate  # noqa: E402


class RegistryMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "tests" / "fixtures" / "registry_cases.json"
        cls.cases = json.loads(fixture.read_text(encoding="utf-8"))

    def test_all_seven_ecosystem_fixtures_normalize(self):
        for ecosystem, case in self.cases.items():
            with self.subTest(ecosystem=ecosystem):
                result = normalize(ecosystem, case["package"], case["payload"])
                self.assertEqual(2, len(result["releases"]))
                self.assertTrue(all(item["published_at"].endswith("Z") for item in result["releases"]))

    def test_python_wheel_filename_versions_are_detected(self):
        result = normalize("python", "demo-pkg", self.cases["python"]["payload"])
        self.assertEqual(["1.0.0", "1.1.0"], [item["version"] for item in result["releases"]])

    def test_private_registry_missing_time_reaches_fail_closed_policy(self):
        normalized = normalize("npm", "private-demo", {
            "versions": {"1.1.0": {"name": "private-demo"}},
            "time": {},
            "auth_token": "must-not-appear",
        })
        decision = evaluate({
            **normalized,
            "current_version": "1.0.0",
            "proposed_version": "1.1.0",
            "now": "2026-01-03T00:00:00Z",
        })
        self.assertEqual("blocked", decision.action)
        self.assertNotIn("must-not-appear", json.dumps(decision.to_json()))

    def test_mutable_action_tag_is_marked_and_blocked(self):
        normalized = normalize("github-actions", "example/action", [
            {"tag_name": "v4", "published_at": "2025-12-01T00:00:00Z"},
        ])
        decision = evaluate({
            **normalized,
            "current_version": "v3.0.0",
            "proposed_version": "v4",
            "now": "2026-01-03T00:00:00Z",
        })
        self.assertEqual("blocked", decision.action)
        self.assertIn("mutable", decision.reasons[0])

    def test_invalid_payload_error_does_not_echo_secrets(self):
        with self.assertRaises(MetadataError) as context:
            normalize("npm", "private-demo", {"token": "must-not-appear"})
        self.assertNotIn("must-not-appear", str(context.exception))


if __name__ == "__main__":
    unittest.main()
