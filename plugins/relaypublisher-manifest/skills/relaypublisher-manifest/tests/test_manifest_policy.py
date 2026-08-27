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


VALID_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def valid_azure_blob_source(**overrides):
    source = {
        "Type": "azureBlob",
        "AccountName": "examplepackages",
        "Container": "intune-packages",
        "BlobName": "contoso/1.0.0/Contoso.pkg",
        "Destination": "Contoso.pkg",
        "Sha256": VALID_SHA256,
        "Auth": {"Type": "workloadIdentity"},
    }
    source.update(overrides)
    return source


def base_pkg_app(**overrides):
    app = {
        "Platform": "macos",
        "Architecture": "arm64",
        "InstallerType": "pkg",
        "AppType": "pkg",
        "Source": valid_azure_blob_source(),
        "Requirements": {"MinimumOSVersion": "13.0"},
        "Detection": {
            "IncludedApps": [
                {"BundleId": "com.example.client", "BundleVersion": "1.0.0"},
            ],
        },
    }
    app.update(overrides)
    return app


def base_windows_app(**overrides):
    app = {
        "Platform": "windows",
        "Architecture": "x64",
        "InstallerType": "win32",
        "Package": {
            "IntuneWin": {"SetupFile": "install.ps1"},
            "RepositoryFiles": [
                {"Source": "scripts/install.ps1", "Destination": "install.ps1"},
            ],
            "ExternalFiles": [
                {
                    "Type": "publicHttp",
                    "Url": "https://example.com/downloads/contoso-tool-1.0.0-x64.exe",
                    "Destination": "bin/contoso-tool.exe",
                    "Sha256": VALID_SHA256,
                },
            ],
        },
        "Install": {
            "CommandLine": r"powershell.exe -ExecutionPolicy Bypass -File .\install.ps1",
            "UninstallCommandLine": r"powershell.exe -ExecutionPolicy Bypass -File .\uninstall.ps1",
            "InstallExperience": "system",
            "RestartBehavior": "suppress",
        },
        "Detection": {
            "Type": "script",
            "ScriptFile": "scripts/detect.ps1",
        },
        "Requirements": {"MinimumOSVersion": "10.0.19045", "Architecture": "x64"},
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

    def test_unsupported_platform_is_rejected(self):
        linux_app = {"Platform": "linux", "InstallerType": "deb"}
        findings = evaluate(manifest_with_apps(linux_app))
        self.assertIn("RP013", codes(errors(findings)))

    def test_missing_architecture_is_rejected(self):
        app = base_pkg_app()
        del app["Architecture"]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP014", codes(errors(findings)))

    def test_unsupported_architecture_is_rejected(self):
        app = base_pkg_app(Architecture="arm")
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP014", codes(errors(findings)))

    def test_missing_minimum_os_version_is_rejected(self):
        app = base_pkg_app(Requirements={})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP015", codes(errors(findings)))

    def test_requirements_architecture_mismatch_is_rejected(self):
        app = base_pkg_app(Requirements={"MinimumOSVersion": "13.0", "Architecture": "x64"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP016", codes(errors(findings)))

    def test_requirements_architecture_match_is_valid(self):
        app = base_pkg_app(Requirements={"MinimumOSVersion": "13.0", "Architecture": "arm64"})
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

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


class SourceItemTests(unittest.TestCase):
    """RP020-RP027: the source-item shape shared by macOS Source and Windows ExternalFiles."""

    def test_unsupported_source_type_is_rejected(self):
        app = base_pkg_app(Source=valid_azure_blob_source(Type="ftp"))
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP020", codes(errors(findings)))

    def test_missing_destination_is_rejected(self):
        source = valid_azure_blob_source()
        del source["Destination"]
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP021", codes(errors(findings)))

    def test_invalid_sha256_is_rejected(self):
        app = base_pkg_app(Source=valid_azure_blob_source(Sha256="not-a-sha256"))
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP022", codes(errors(findings)))

    def test_public_http_requires_url(self):
        source = {
            "Type": "publicHttp",
            "Destination": "bin/tool.exe",
            "Sha256": VALID_SHA256,
        }
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP023", codes(errors(findings)))

    def test_github_release_requires_owner_repository_tag_asset_name(self):
        source = {
            "Type": "githubRelease",
            "Destination": "bin/tool.exe",
            "Sha256": VALID_SHA256,
        }
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        error_codes_by_path = {f.path for f in errors(findings)}
        for field in ("Owner", "Repository", "Tag", "AssetName"):
            self.assertIn(f"Apps[0].Source.{field}", error_codes_by_path)

    def test_azure_blob_requires_account_container_blob_name(self):
        source = {
            "Type": "azureBlob",
            "Destination": "bin/tool.exe",
            "Sha256": VALID_SHA256,
            "Auth": {"Type": "workloadIdentity"},
        }
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        error_codes_by_path = {f.path for f in errors(findings)}
        for field in ("AccountName", "Container", "BlobName"):
            self.assertIn(f"Apps[0].Source.{field}", error_codes_by_path)

    def test_unsupported_auth_type_is_rejected(self):
        app = base_pkg_app(Source=valid_azure_blob_source(Auth={"Type": "basic"}))
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP024", codes(errors(findings)))

    def test_token_auth_requires_secret_name(self):
        source = {
            "Type": "publicHttp",
            "Url": "https://example.com/tool.exe",
            "Destination": "bin/tool.exe",
            "Sha256": VALID_SHA256,
            "Auth": {"Type": "token"},
        }
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP025", codes(errors(findings)))

    def test_github_release_forbids_workload_identity(self):
        source = {
            "Type": "githubRelease",
            "Owner": "contoso",
            "Repository": "tool",
            "Tag": "v1.0.0",
            "AssetName": "tool.exe",
            "Destination": "bin/tool.exe",
            "Sha256": VALID_SHA256,
            "Auth": {"Type": "workloadIdentity"},
        }
        app = base_pkg_app(Source=source)
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP026", codes(errors(findings)))

    def test_azure_blob_requires_workload_identity(self):
        app = base_pkg_app(Source=valid_azure_blob_source(Auth={"Type": "none"}))
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP027", codes(errors(findings)))

    def test_valid_source_has_no_errors(self):
        app = base_pkg_app()
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])


class WindowsEvaluateDictTests(unittest.TestCase):
    """Windows Win32 structural checks: RP029-RP041."""

    def test_valid_windows_win32_has_no_errors(self):
        findings = evaluate(manifest_with_apps(base_windows_app()))
        self.assertEqual(errors(findings), [])

    def test_unsupported_installer_type_is_rejected(self):
        app = base_windows_app(InstallerType="msi")
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP029", codes(errors(findings)))

    def test_app_type_on_windows_is_rejected(self):
        app = base_windows_app(AppType="pkg")
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP030", codes(errors(findings)))

    def test_source_on_windows_is_rejected(self):
        app = base_windows_app(Source=valid_azure_blob_source())
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP031", codes(errors(findings)))

    def test_missing_package_is_rejected(self):
        app = base_windows_app()
        del app["Package"]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP032", codes(errors(findings)))

    def test_missing_intune_win_setup_file_is_rejected(self):
        app = base_windows_app()
        app["Package"] = dict(app["Package"])
        app["Package"]["IntuneWin"] = {}
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP033", codes(errors(findings)))

    def test_repository_file_missing_destination_is_rejected(self):
        app = base_windows_app()
        app["Package"] = dict(app["Package"])
        app["Package"]["RepositoryFiles"] = [{"Source": "scripts/install.ps1"}]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP034", codes(errors(findings)))

    def test_external_file_invalid_source_is_rejected(self):
        app = base_windows_app()
        app["Package"] = dict(app["Package"])
        app["Package"]["ExternalFiles"] = [{"Type": "publicHttp", "Destination": "bin/tool.exe"}]
        findings = evaluate(manifest_with_apps(app))
        # Missing Sha256 (RP022) and missing Url for publicHttp (RP023).
        self.assertIn("RP022", codes(errors(findings)))
        self.assertIn("RP023", codes(errors(findings)))

    def test_missing_install_is_rejected(self):
        app = base_windows_app()
        del app["Install"]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP035", codes(errors(findings)))

    def test_missing_command_lines_are_rejected(self):
        app = base_windows_app()
        app["Install"] = {"InstallExperience": "system", "RestartBehavior": "suppress"}
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP036", codes(errors(findings)))

    def test_unsupported_install_experience_is_rejected(self):
        app = base_windows_app()
        app["Install"] = dict(app["Install"])
        app["Install"]["InstallExperience"] = "kiosk"
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP037", codes(errors(findings)))

    def test_unsupported_restart_behavior_is_rejected(self):
        app = base_windows_app()
        app["Install"] = dict(app["Install"])
        app["Install"]["RestartBehavior"] = "reboot"
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP038", codes(errors(findings)))

    def test_unsupported_return_code_type_is_rejected(self):
        app = base_windows_app()
        app["Install"] = dict(app["Install"])
        app["Install"]["ReturnCodes"] = [{"Code": 1602, "Type": "cancelled"}]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP039", codes(errors(findings)))

    def test_valid_return_codes_have_no_errors(self):
        app = base_windows_app()
        app["Install"] = dict(app["Install"])
        app["Install"]["ReturnCodes"] = [{"Code": 0, "Type": "success"}, {"Code": 3010, "Type": "softReboot"}]
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_missing_detection_is_rejected(self):
        app = base_windows_app()
        del app["Detection"]
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP040", codes(errors(findings)))

    def test_unsupported_detection_type_is_rejected(self):
        app = base_windows_app(Detection={"Type": "msi", "ScriptFile": "scripts/detect.ps1"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP040", codes(errors(findings)))

    def test_missing_detection_script_file_is_rejected(self):
        app = base_windows_app(Detection={"Type": "script"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP041", codes(errors(findings)))

    def test_arm64_windows_has_no_errors(self):
        app = base_windows_app(Architecture="arm64", Requirements={"MinimumOSVersion": "10.0.22621", "Architecture": "arm64"})
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])


class CrossPlatformFieldMisuseTests(unittest.TestCase):
    """RP003/RP044: fields belonging to the other platform must not leak across entries."""

    def test_package_on_macos_is_rejected(self):
        app = base_pkg_app(Package={"IntuneWin": {"SetupFile": "install.ps1"}})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP003", codes(errors(findings)))

    def test_install_on_macos_is_rejected(self):
        app = base_pkg_app(Install={"CommandLine": "true"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP003", codes(errors(findings)))

    def test_detection_type_on_macos_is_rejected(self):
        app = base_pkg_app(
            Detection={
                "Type": "script",
                "IncludedApps": [{"BundleId": "com.example.client", "BundleVersion": "1.0.0"}],
            }
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP044", codes(errors(findings)))


VALID_GROUP_ID = "00000000-0000-0000-0000-000000000001"
OTHER_GROUP_ID = "00000000-0000-0000-0000-000000000002"
VALID_FILTER_ID = "00000000-0000-0000-0000-0000000000ff"


class AssignmentsTests(unittest.TestCase):
    """RP050-RP058: the `Assignments` block, shared by Windows and macOS entries."""

    def test_valid_group_assignment_has_no_errors(self):
        app = base_pkg_app(Assignments=[{"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_valid_all_devices_assignment_has_no_errors(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_unsupported_target_is_rejected(self):
        app = base_pkg_app(Assignments=[{"Target": "allComputers", "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP050", codes(errors(findings)))

    def test_group_id_required_for_group_target(self):
        app = base_pkg_app(Assignments=[{"Target": "group", "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP051", codes(errors(findings)))

    def test_group_id_must_be_guid(self):
        app = base_pkg_app(Assignments=[{"Target": "group", "GroupId": "not-a-guid", "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP051", codes(errors(findings)))

    def test_group_id_forbidden_for_non_group_target(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "GroupId": VALID_GROUP_ID, "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP051", codes(errors(findings)))

    def test_unsupported_mode_is_rejected(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Mode": "sometimes", "Intent": "required"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP052", codes(errors(findings)))

    def test_intent_required_for_include_mode(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Mode": "include"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP053", codes(errors(findings)))

    def test_intent_not_required_for_exclude_mode(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Mode": "exclude"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_unsupported_intent_is_rejected(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Intent": "delete"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP053", codes(errors(findings)))

    def test_filter_id_must_be_guid(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Intent": "required", "FilterId": "not-a-guid", "FilterMode": "include"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP054", codes(errors(findings)))

    def test_filter_mode_required_when_filter_id_set(self):
        app = base_pkg_app(Assignments=[{"Target": "allDevices", "Intent": "required", "FilterId": VALID_FILTER_ID}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP055", codes(errors(findings)))

    def test_valid_filter_has_no_errors(self):
        app = base_pkg_app(
            Assignments=[{"Target": "allDevices", "Intent": "required", "FilterId": VALID_FILTER_ID, "FilterMode": "include"}]
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_unsupported_notifications_is_rejected(self):
        app = base_windows_app(Assignments=[{"Target": "allDevices", "Intent": "required", "Settings": {"Notifications": "showSome"}}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP056", codes(errors(findings)))

    def test_valid_notifications_has_no_errors(self):
        app = base_windows_app(
            Assignments=[{"Target": "allDevices", "Intent": "required", "Settings": {"Notifications": "showReboot", "RestartGracePeriodMinutes": 60}}]
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_duplicate_target_is_rejected(self):
        app = base_pkg_app(
            Assignments=[
                {"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "required"},
                {"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "available"},
            ]
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP057", codes(errors(findings)))

    def test_same_group_different_mode_is_not_duplicate(self):
        app = base_pkg_app(
            Assignments=[
                {"Target": "group", "GroupId": VALID_GROUP_ID, "Mode": "include", "Intent": "required"},
                {"Target": "group", "GroupId": VALID_GROUP_ID, "Mode": "exclude"},
            ]
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_different_groups_are_not_duplicates(self):
        app = base_pkg_app(
            Assignments=[
                {"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "required"},
                {"Target": "group", "GroupId": OTHER_GROUP_ID, "Intent": "available"},
            ]
        )
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_uninstall_intent_forbidden_for_macos_pkg(self):
        app = base_pkg_app(Assignments=[{"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "uninstall"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP058", codes(errors(findings)))

    def test_uninstall_intent_allowed_for_macos_lob(self):
        app = base_pkg_app(
            AppType="lob",
            Detection={
                "IncludedApps": [{"BundleId": "com.example.client", "BundleVersion": "1.0.0", "BundleBuildVersion": "1"}],
            },
            Assignments=[{"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "uninstall"}],
        )
        findings = evaluate(manifest_with_apps(app, Icon="icons/contoso.png"))
        self.assertEqual(errors(findings), [])

    def test_uninstall_intent_allowed_for_windows(self):
        app = base_windows_app(Assignments=[{"Target": "group", "GroupId": VALID_GROUP_ID, "Intent": "uninstall"}])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_omitted_assignments_has_no_errors(self):
        findings = evaluate(manifest_with_apps(base_pkg_app()))
        self.assertEqual(errors(findings), [])


class CategoriesTests(unittest.TestCase):
    """RP060-RP062: the `Categories` field, shared by Windows and macOS entries."""

    def test_valid_categories_have_no_errors(self):
        app = base_pkg_app(Categories=["Business Apps", "Productivity"])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_omitted_categories_has_no_errors(self):
        findings = evaluate(manifest_with_apps(base_pkg_app()))
        self.assertEqual(errors(findings), [])

    def test_empty_categories_list_has_no_errors(self):
        app = base_pkg_app(Categories=[])
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_blank_category_is_rejected(self):
        app = base_pkg_app(Categories=["Business Apps", "   "])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP060", codes(errors(findings)))

    def test_outer_whitespace_is_rejected(self):
        app = base_pkg_app(Categories=[" Business Apps"])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP061", codes(errors(findings)))

    def test_case_insensitive_duplicate_is_rejected(self):
        app = base_pkg_app(Categories=["Business Apps", "business apps"])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP062", codes(errors(findings)))

    def test_exact_duplicate_is_rejected(self):
        app = base_pkg_app(Categories=["Business Apps", "Business Apps"])
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP062", codes(errors(findings)))


class MacOsScriptsTests(unittest.TestCase):
    """RP070-RP079: the macOS `Scripts` (pre/post-install) block, AppType: pkg only."""

    def test_valid_scripts_have_no_errors(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/macos/tool/preinstall.sh", "PostInstall": "scripts/macos/tool/postinstall.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_only_pre_install_is_valid(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/macos/tool/preinstall.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])

    def test_omitted_scripts_has_no_errors(self):
        findings = evaluate(manifest_with_apps(base_pkg_app()))
        self.assertEqual(errors(findings), [])

    def test_scripts_on_windows_is_rejected(self):
        app = base_windows_app(Scripts={"PreInstall": "scripts/preinstall.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP070", codes(errors(findings)))

    def test_scripts_on_macos_lob_is_rejected(self):
        app = base_pkg_app(
            AppType="lob",
            Detection={
                "IncludedApps": [{"BundleId": "com.example.client", "BundleVersion": "1.0.0", "BundleBuildVersion": "1"}],
            },
            Scripts={"PreInstall": "scripts/preinstall.sh"},
        )
        findings = evaluate(manifest_with_apps(app, Icon="icons/contoso.png"))
        self.assertIn("RP070", codes(errors(findings)))

    def test_both_null_scripts_is_rejected(self):
        app = base_pkg_app(Scripts={})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP071", codes(errors(findings)))

    def test_absolute_path_is_rejected(self):
        app = base_pkg_app(Scripts={"PreInstall": "/etc/preinstall.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP072", codes(errors(findings)))

    def test_traversal_path_is_rejected(self):
        app = base_pkg_app(Scripts={"PreInstall": "../preinstall.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP072", codes(errors(findings)))

    def test_wrong_extension_is_rejected(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/preinstall.py"})
        findings = evaluate(manifest_with_apps(app))
        self.assertIn("RP073", codes(errors(findings)))

    def test_missing_script_file_is_rejected_with_repo_root(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/does-not-exist.sh"})
        findings = evaluate(manifest_with_apps(app), repo_root=FIXTURES)
        self.assertIn("RP074", codes(errors(findings)))

    def test_valid_script_file_has_no_errors_with_repo_root(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/valid-preinstall.sh"})
        findings = evaluate(manifest_with_apps(app), repo_root=FIXTURES)
        self.assertEqual(errors(findings), [])

    def test_bom_script_file_is_rejected_with_repo_root(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/with-bom.sh"})
        findings = evaluate(manifest_with_apps(app), repo_root=FIXTURES)
        self.assertIn("RP075", codes(errors(findings)))

    def test_no_shebang_script_file_is_rejected_with_repo_root(self):
        app = base_pkg_app(Scripts={"PreInstall": "scripts/no-shebang.sh"})
        findings = evaluate(manifest_with_apps(app), repo_root=FIXTURES)
        self.assertIn("RP078", codes(errors(findings)))

    def test_script_shape_only_check_without_repo_root(self):
        # No --repo-root supplied: only path shape/extension are checked, matching Icon's
        # existing behavior. A nonexistent file is not itself an error here.
        app = base_pkg_app(Scripts={"PreInstall": "scripts/does-not-exist.sh"})
        findings = evaluate(manifest_with_apps(app))
        self.assertEqual(errors(findings), [])


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
            "valid-windows-win32-x64.yaml",
            "valid-windows-win32-arm64.yaml",
            "valid-assignments-categories-scripts.yaml",
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
            "invalid-unsupported-platform.yaml": "RP013",
            "invalid-windows-apptype-set.yaml": "RP030",
            "invalid-windows-missing-package.yaml": "RP032",
            "invalid-windows-bad-restart-behavior.yaml": "RP038",
            "invalid-assignment-duplicate-target.yaml": "RP057",
            "invalid-categories-duplicate.yaml": "RP062",
            "invalid-scripts-on-windows.yaml": "RP070",
        }
        for name, expected_code in expectations.items():
            with self.subTest(fixture=name):
                findings = evaluate(self._load(name), repo_root=FIXTURES)
                self.assertIn(expected_code, codes(errors(findings)), f"{name}: {findings}")


if __name__ == "__main__":
    unittest.main()
