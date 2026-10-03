from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from release_policy import (  # noqa: E402
    ReleaseRecord,
    evaluate,
    maven_key,
    pep440_key,
    select_eligible_release,
    semver_key,
)


NOW = "2026-01-03T00:00:00Z"


def payload(**overrides):
    value = {
        "ecosystem": "npm",
        "package": "demo",
        "current_version": "1.0.0",
        "proposed_version": "1.1.0",
        "now": NOW,
        "releases": [
            {"version": "1.0.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "1.1.0", "published_at": "2026-01-02T00:00:00Z"},
        ],
    }
    value.update(overrides)
    return value


class ReleasePolicyTests(unittest.TestCase):
    def test_exactly_24_hours_is_eligible(self):
        decision = evaluate(payload())
        self.assertEqual("merge", decision.action)
        self.assertEqual("1.1.0", decision.eligible_version)

    def test_23_59_59_is_not_eligible(self):
        decision = evaluate(payload(releases=[
            {"version": "1.0.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "1.1.0", "published_at": "2026-01-02T00:00:01Z"},
        ]))
        self.assertEqual("blocked", decision.action)

    def test_timezone_offsets_are_normalized(self):
        decision = evaluate(payload(releases=[
            {"version": "1.0.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "1.1.0", "published_at": "2026-01-02T09:00:00+09:00"},
        ]))
        self.assertEqual("merge", decision.action)
        self.assertEqual("2026-01-02T00:00:00Z", decision.published_at)

    def test_future_timestamp_fails_closed(self):
        decision = evaluate(payload(releases=[
            {"version": "1.1.0", "published_at": "2026-01-04T00:00:00Z"},
        ]))
        self.assertEqual("blocked", decision.action)
        self.assertIn("future", decision.reasons[0])

    def test_latest_stable_is_selected_across_majors(self):
        decision = evaluate(payload(releases=[
            {"version": "1.1.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "2.0.0", "published_at": "2025-12-02T00:00:00Z"},
            {"version": "3.0.0-rc.1", "published_at": "2025-12-03T00:00:00Z"},
        ]))
        self.assertEqual("major-plan", decision.action)
        self.assertEqual("2.0.0", decision.eligible_version)
        self.assertTrue(decision.refresh_required)

    def test_newer_compatible_target_requires_refresh(self):
        decision = evaluate(payload(releases=[
            {"version": "1.1.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "1.2.0", "published_at": "2025-12-02T00:00:00Z"},
        ]))
        self.assertEqual("refresh", decision.action)
        self.assertEqual("1.2.0", decision.eligible_version)

    def test_zero_minor_change_is_a_compatibility_boundary(self):
        decision = evaluate(payload(
            current_version="0.3.5",
            proposed_version="0.4.0",
            releases=[{"version": "0.4.0", "published_at": "2025-12-01T00:00:00Z"}],
        ))
        self.assertEqual("major-plan", decision.action)

    def test_prerelease_yanked_retracted_unlisted_and_deprecated_are_excluded(self):
        decision = evaluate(payload(releases=[
            {"version": "1.1.0", "published_at": "2025-12-01T00:00:00Z"},
            {"version": "1.2.0-alpha.1", "published_at": "2025-12-02T00:00:00Z"},
            {"version": "1.3.0", "published_at": "2025-12-03T00:00:00Z", "yanked": True},
            {"version": "1.4.0", "published_at": "2025-12-04T00:00:00Z", "retracted": True},
            {"version": "1.5.0", "published_at": "2025-12-05T00:00:00Z", "listed": False},
            {"version": "1.6.0", "published_at": "2025-12-06T00:00:00Z", "deprecated": True},
        ]))
        self.assertEqual("merge", decision.action)
        self.assertEqual("1.1.0", decision.eligible_version)

    def test_non_comparable_release_blocks(self):
        decision = evaluate(payload(releases=[
            {"version": "release-next", "published_at": "2025-12-01T00:00:00Z"},
        ]))
        self.assertEqual("blocked", decision.action)
        self.assertIn("non-comparable", decision.reasons[0])

    def test_missing_timestamp_blocks_private_registry(self):
        decision = evaluate(payload(releases=[{"version": "1.1.0", "published_at": None}]))
        self.assertEqual("blocked", decision.action)
        self.assertIn("timestamp", decision.reasons[0])

    def test_security_update_has_no_age_exception(self):
        decision = evaluate(payload(
            security_update=True,
            releases=[{"version": "1.1.0", "published_at": "2026-01-02T00:00:01Z"}],
        ))
        self.assertEqual("blocked", decision.action)

    def test_proposed_release_newer_than_age_eligible_release_blocks(self):
        decision = evaluate(payload(
            proposed_version="1.2.0",
            releases=[
                {"version": "1.1.0", "published_at": "2025-12-01T00:00:00Z"},
                {"version": "1.2.0", "published_at": "2026-01-02T12:00:00Z"},
            ],
        ))
        self.assertEqual("blocked", decision.action)

    def test_semver_pep440_maven_and_go_ordering(self):
        self.assertGreater(semver_key("2.0.0"), semver_key("1.99.0"))
        self.assertGreater(semver_key("v1.2.0"), semver_key("v1.1.9"))
        self.assertGreater(pep440_key("1.0.post1"), pep440_key("1.0"))
        self.assertLess(pep440_key("1.0rc1"), pep440_key("1.0"))
        self.assertGreater(maven_key("2.0.0"), maven_key("1.99.0"))

    def test_selection_api_accepts_exact_boundary(self):
        selected = select_eligible_release(
            "npm",
            [ReleaseRecord("1.0.0", "2026-01-02T00:00:00Z")],
            datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
        self.assertEqual("1.0.0", selected.version)


if __name__ == "__main__":
    unittest.main()
