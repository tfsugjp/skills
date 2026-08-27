from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from manifest_policy import evaluate  # noqa: E402

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def errors(findings):
    return [f for f in findings if f.severity == "error"]


def codes(findings):
    return {f.code for f in findings}


def base_pkg_app(**overrides):
    app = {
        "Platform": "macos",
        "Architecture": "arm64",
        "InstallerType": "pkg",
        "AppType": "pkg",
        "Source": {"Type": "azureBlob"},
        "Requirements": {"MinimumOSVersion": "13.0"},
        "Detection": {
            "IncludedApps": [
                {"BundleId": "com.example.client", "BundleVersion": "1.0.0"},
            ],
        },
    }
    app.update(overrides)
    return app


def manifest_with_apps(*apps, **root_overrides):
    manifest = {"PackageIdentifier": "Contoso.Test", "PackageVersion": "1.0.0", "Apps": list(apps)}
    manifest.update(root_overrides)
    return manifest


class EvaluateDictTests(unittest.TestCase):
    """Tests against dicts directly — no PyYAML dependency required."""

    def test_valid_pkg_multibundle_has_no_errors(self):
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.client",
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "4.2.0"},
                    {"BundleId": "com.example.helper", "BundleVersion": "4.2.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_valid_lob_multibundle_has_no_errors(self):
        app = base_pkg_app(
            AppType="lob",
            Detection={
                "PrimaryBundleId": "com.example.lob.main",
                "IncludedApps": [
                    {"BundleId": "com.example.lob.main", "BundleVersion": "4.2.0", "BundleBuildVersion": "4200"},
                    {"BundleId": "com.example.lob.helper", "BundleVersion": "4.2.0", "BundleBuildVersion": "4200"},
                ],
            },
        )
        findings = evaluate(manifest_with_apps(app, Icon="icons/contoso.png"))
        self.assertEqual(errors(findings), [])

    def test_dmg_installer_type_is_rejected(self):
        app = base_pkg_app(InstallerType="dmg")
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP001", codes(errors(findings)))

    def test_unsupported_app_type_is_rejected(self):
        app = base_pkg_app(AppType="dmg")
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP002", codes(errors(findings)))

    def test_windows_only_fields_on_macos_entry_are_rejected(self):
        app = base_pkg_app(Package={"Type": "msi"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP003", codes(errors(findings)))

    def test_missing_source_is_rejected(self):
        app = base_pkg_app()
        del app["Source"]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP003", codes(errors(findings)))

    def test_included_apps_count_out_of_range_is_rejected(self):
        app = base_pkg_app(Detection={"IncludedApps": []})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP004", codes(errors(findings)))

    def test_included_apps_over_500_is_rejected(self):
        entries = [{"BundleId": f"com.example.app{i}", "BundleVersion": "1.0.0"} for i in range(501)]
        app = base_pkg_app(Detection={"IncludedApps": entries})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP004", codes(errors(findings)))

    def test_empty_bundle_id_is_rejected(self):
        app = base_pkg_app(Detection={"IncludedApps": [{"BundleId": "  ", "BundleVersion": "1.0.0"}]})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP005", codes(errors(findings)))

    def test_missing_bundle_version_is_rejected(self):
        app = base_pkg_app(Detection={"IncludedApps": [{"BundleId": "com.example.client"}]})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP005", codes(errors(findings)))

    def test_duplicate_bundle_id_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.1"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP006", codes(errors(findings)))

    def test_duplicate_check_is_case_sensitive(self):
        app = base_pkg_app(
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.Client", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.1"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertNotIn("RP006", codes(errors(findings)))

    def test_lob_missing_build_version_is_rejected(self):
        app = base_pkg_app(
            AppType="lob",
            Detection={"IncludedApps": [{"BundleId": "com.example.client", "BundleVersion": "1.0.0"}]},
        )
        findings = evaluate(manifest_with_apps(app, Icon="icons/contoso.png"))
        self.assertIn("RP007", codes(errors(findings)))

    def test_pkg_with_build_version_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0", "BundleBuildVersion": "1000"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP008", codes(errors(findings)))

    def test_blank_primary_bundle_id_is_rejected(self):
        app = base_pkg_app(Detection={"PrimaryBundleId": "   ", "IncludedApps": [{"BundleId": "com.example.client", "BundleVersion": "1.0.0"}]})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP009", codes(errors(findings)))

    def test_primary_bundle_id_exact_match_is_valid(self):
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.client",
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.helper", "BundleVersion": "1.0.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_primary_bundle_id_dot_prefix_match_is_valid(self):
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.client",
                "IncludedApps": [
                    {"BundleId": "com.example.client.main", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.helper", "BundleVersion": "1.0.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_primary_bundle_id_ambiguous_match_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.client",
                "IncludedApps": [
                    {"BundleId": "com.example.client.main", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.client.agent", "BundleVersion": "1.0.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP010", codes(errors(findings)))

    def test_primary_bundle_id_no_match_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.app",
                "IncludedApps": [{"BundleId": "com.example.application", "BundleVersion": "1.0.0"}],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP010", codes(errors(findings)))

    def test_primary_bundle_id_segment_boundary_is_respected(self):
        # com.example.app must NOT match com.example.application (no dot boundary).
        app = base_pkg_app(
            Detection={
                "PrimaryBundleId": "com.example.app",
                "IncludedApps": [
                    {"BundleId": "com.example.application", "BundleVersion": "1.0.0"},
                    {"BundleId": "com.example.app.helper", "BundleVersion": "1.0.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        # Exactly one match (com.example.app.helper) — not ambiguous, not unresolved.
        self.assertEqual(errors(findings), [])

    def test_lob_without_root_icon_is_rejected(self):
        app = base_pkg_app(
            AppType="lob",
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0", "BundleBuildVersion": "1000"},
                ],
            },
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP011", codes(errors(findings)))

    def test_unknown_included_app_field_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0", "ExcludeFromDetection": True},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP012", codes(errors(findings)))

    def test_updater_omission_is_not_flagged(self):
        # A PKG that contains an updater the manifest author chose to omit
        # from IncludedApps must validate cleanly — omission is the correct
        # exclusion mechanism, not an error.
        app = base_pkg_app(
            Detection={
                "IncludedApps": [
                    {"BundleId": "com.example.client", "BundleVersion": "1.0.0"},
                ],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_non_macos_entry_is_skipped_not_checked(self):
        windows_app = {"Platform": "windows", "InstallerType": "exe"}
        findings = evaluate(manifest_with_apps(windows_app))
        self.assertEqual(errors(findings), [])
        self.assertIn("RP-SKIP", codes(findings))

    def test_default_app_type_is_treated_as_pkg(self):
        app = base_pkg_app()
        del app["AppType"]
        app["Detection"] = {
            "IncludedApps": [
                {"BundleId": "com.example.client", "BundleVersion": "1.0.0", "BundleBuildVersion": "1000"},
            ],
        }
        findings = evaluate(manifest_with_apps(app))
        # Treated as pkg, so a present BundleBuildVersion is flagged (RP008).
        self.assertIn("RP008", codes(errors(findings)))

    def test_evaluate_does_not_mutate_input(self):
        app = base_pkg_app()
        manifest = manifest_with_apps(app)
        before = copy.deepcopy(manifest)
        evaluate(manifest)
        self.assertEqual(manifest, before)


@unittest.skipUnless(HAS_YAML, "PyYAML is not installed")
class FixtureFileTests(unittest.TestCase):
    """End-to-end tests that load the checked-in YAML fixtures."""

    def _load(self, name: str) -> dict:
        with (FIXTURES / name).open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)

    def test_valid_fixtures_have_no_errors(self):
        for name in (
            "valid-pkg-multibundle.yaml",
            "valid-lob-multibundle.yaml",
            "valid-primary-prefix-match.yaml",
        ):
            with self.subTest(fixture=name):
                findings = evaluate(self._load(name), repo_root=FIXTURES)
                self.assertEqual(errors(findings), [], f"{name}: {errors(findings)}")

    def test_invalid_fixtures_are_rejected(self):
        expectations = {
            "invalid-dmg.yaml": "RP001",
            "invalid-ambiguous-primary.yaml": "RP010",
            "invalid-unresolved-primary.yaml": "RP010",
            "invalid-duplicate-bundleid.yaml": "RP006",
            "invalid-lob-missing-build.yaml": "RP007",
            "invalid-pkg-with-build.yaml": "RP008",
        }
        for name, expected_code in expectations.items():
            with self.subTest(fixture=name):
                findings = evaluate(self._load(name), repo_root=FIXTURES)
                self.assertIn(expected_code, codes(errors(findings)), f"{name}: {findings}")


if __name__ == "__main__":
    unittest.main()
