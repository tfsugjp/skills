#!/usr/bin/env python3
"""Statically check a Relaypublisher manifest against the macOS PKG/LOB contract.

This is a bundled, CLI-independent checker for the invariants documented in
``references/macos-manifest.md``. It is not the Relaypublisher schema
validator and passing it is not equivalent to a passing
``relaypublisher validate`` run: it only catches the manifest-authoring
mistakes this skill is responsible for (unsupported DMG entries, malformed
``IncludedApps``, ambiguous or unresolved primary-bundle selectors, and
LOB/PKG field misuse). It never downloads, unpacks, or inspects a package,
and it never calls Microsoft Graph or changes tenant state.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SUPPORTED_APP_TYPES = {"pkg", "lob"}
DEFAULT_APP_TYPE = "pkg"
WINDOWS_ONLY_KEYS = ("Package", "Install")
ALLOWED_INCLUDED_APP_KEYS = {"BundleId", "BundleVersion", "BundleBuildVersion"}
MIN_INCLUDED_APPS = 1
MAX_INCLUDED_APPS = 500


class MissingDependencyError(RuntimeError):
    """Raised when PyYAML is required but not installed."""


@dataclass(frozen=True)
class Finding:
    """One contract check result."""

    code: str
    severity: str  # "error" or "info"
    path: str
    message: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _finding(code: str, severity: str, path: str, message: str) -> Finding:
    return Finding(code=code, severity=severity, path=path, message=message)


def _is_nonblank_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _resolve_primary(selector: str, bundle_ids: list[str]) -> list[str]:
    """Return every bundle id that matches `selector` under the dot-prefix rule."""
    matches = []
    for bundle_id in bundle_ids:
        if bundle_id == selector or bundle_id.startswith(selector + "."):
            matches.append(bundle_id)
    return matches


def _evaluate_included_apps(
    app_path: str,
    app_type: str,
    included_apps: Any,
) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    bundle_ids: list[str] = []
    apps_path = f"{app_path}.Detection.IncludedApps"

    if not isinstance(included_apps, list):
        findings.append(_finding("RP004", "error", apps_path, "IncludedApps must be a list"))
        return findings, bundle_ids

    if not (MIN_INCLUDED_APPS <= len(included_apps) <= MAX_INCLUDED_APPS):
        findings.append(
            _finding(
                "RP004",
                "error",
                apps_path,
                f"IncludedApps must contain {MIN_INCLUDED_APPS}-{MAX_INCLUDED_APPS} entries, "
                f"found {len(included_apps)}",
            )
        )

    seen: set[str] = set()
    for index, entry in enumerate(included_apps):
        entry_path = f"{apps_path}[{index}]"
        if not isinstance(entry, dict):
            findings.append(_finding("RP005", "error", entry_path, "entry must be a mapping"))
            continue

        unknown_keys = sorted(set(entry) - ALLOWED_INCLUDED_APP_KEYS)
        if unknown_keys:
            findings.append(
                _finding(
                    "RP012",
                    "error",
                    entry_path,
                    f"unsupported field(s) {unknown_keys}; exclusion is by omission, not a new field",
                )
            )

        bundle_id = entry.get("BundleId")
        bundle_version = entry.get("BundleVersion")
        if not _is_nonblank_str(bundle_id):
            findings.append(_finding("RP005", "error", f"{entry_path}.BundleId", "BundleId is required and must be non-empty"))
        else:
            bundle_ids.append(bundle_id)
            if bundle_id in seen:
                findings.append(
                    _finding(
                        "RP006",
                        "error",
                        f"{entry_path}.BundleId",
                        f"duplicate BundleId (ordinal, case-sensitive): {bundle_id}",
                    )
                )
            seen.add(bundle_id)

        if not _is_nonblank_str(bundle_version):
            findings.append(
                _finding("RP005", "error", f"{entry_path}.BundleVersion", "BundleVersion is required and must be non-empty")
            )

        build_version = entry.get("BundleBuildVersion")
        if app_type == "lob":
            if not _is_nonblank_str(build_version):
                findings.append(
                    _finding(
                        "RP007",
                        "error",
                        f"{entry_path}.BundleBuildVersion",
                        "BundleBuildVersion is required for every lob entry",
                    )
                )
        elif app_type == "pkg" and "BundleBuildVersion" in entry:
            findings.append(
                _finding(
                    "RP008",
                    "error",
                    f"{entry_path}.BundleBuildVersion",
                    "BundleBuildVersion is not part of the pkg mapping; omit it",
                )
            )

    return findings, bundle_ids


def _evaluate_primary_selector(app_path: str, detection: dict, bundle_ids: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    if "PrimaryBundleId" not in detection:
        return findings

    selector = detection.get("PrimaryBundleId")
    selector_path = f"{app_path}.Detection.PrimaryBundleId"
    if not _is_nonblank_str(selector):
        findings.append(_finding("RP009", "error", selector_path, "PrimaryBundleId must not be empty or whitespace-only"))
        return findings

    matches = _resolve_primary(selector, bundle_ids)
    if len(matches) == 0:
        findings.append(_finding("RP010", "error", selector_path, f"PrimaryBundleId matches no declared bundle: {selector}"))
    elif len(matches) > 1:
        findings.append(
            _finding(
                "RP010",
                "error",
                selector_path,
                f"PrimaryBundleId is ambiguous: {selector} matches {matches}",
            )
        )
    return findings


def _evaluate_macos_app(index: int, app: dict, root: dict, repo_root: Path | None) -> list[Finding]:
    app_path = f"Apps[{index}]"
    findings: list[Finding] = []

    installer_type = app.get("InstallerType")
    if installer_type != "pkg":
        findings.append(
            _finding(
                "RP001",
                "error",
                f"{app_path}.InstallerType",
                f"unsupported macOS InstallerType (only pkg is supported): {installer_type!r}",
            )
        )

    app_type = app.get("AppType", DEFAULT_APP_TYPE)
    if app_type not in SUPPORTED_APP_TYPES:
        findings.append(
            _finding("RP002", "error", f"{app_path}.AppType", f"unsupported AppType (must be pkg or lob): {app_type!r}")
        )
        # Fall back to the default so downstream checks still run meaningfully.
        app_type = DEFAULT_APP_TYPE

    windows_keys = [key for key in WINDOWS_ONLY_KEYS if key in app]
    if windows_keys:
        findings.append(
            _finding(
                "RP003",
                "error",
                app_path,
                f"Windows-only field(s) {windows_keys} must not appear on a macOS entry",
            )
        )
    source = app.get("Source")
    if not isinstance(source, dict):
        findings.append(_finding("RP003", "error", f"{app_path}.Source", "macOS entry must declare exactly one Source object"))

    detection = app.get("Detection")
    bundle_ids: list[str] = []
    if not isinstance(detection, dict):
        findings.append(_finding("RP004", "error", f"{app_path}.Detection", "Detection is required for a macOS entry"))
    else:
        included_findings, bundle_ids = _evaluate_included_apps(app_path, app_type, detection.get("IncludedApps"))
        findings.extend(included_findings)
        findings.extend(_evaluate_primary_selector(app_path, detection, bundle_ids))

    if app_type == "lob" and not _is_nonblank_str(root.get("Icon")):
        findings.append(_finding("RP011", "error", "Icon", "AppType: lob requires a non-empty root Icon path"))
    elif app_type == "lob" and repo_root is not None:
        icon_path = (repo_root / root["Icon"]).resolve()
        if not icon_path.is_file():
            findings.append(_finding("RP011", "error", "Icon", f"Icon path does not exist under repo root: {root['Icon']}"))

    return findings


def evaluate(manifest: dict, repo_root: Path | None = None) -> list[Finding]:
    """Check `manifest` (a parsed dict) against the macOS PKG/LOB contract.

    Pure function: does not touch YAML parsing, the filesystem (unless
    `repo_root` is given, to check an LOB Icon's existence), or the network.
    Non-macOS entries are intentionally left untouched and reported as
    skipped (severity "info") — this contract only governs macOS entries.
    """
    findings: list[Finding] = []
    if not isinstance(manifest, dict):
        return [_finding("RP000", "error", "$", "manifest must be a mapping")]

    apps = manifest.get("Apps")
    if not isinstance(apps, list) or not apps:
        return [_finding("RP000", "error", "Apps", "manifest must declare a non-empty Apps list")]

    for index, app in enumerate(apps):
        app_path = f"Apps[{index}]"
        if not isinstance(app, dict):
            findings.append(_finding("RP000", "error", app_path, "app entry must be a mapping"))
            continue
        platform = app.get("Platform")
        if platform != "macos":
            findings.append(
                _finding(
                    "RP-SKIP",
                    "info",
                    app_path,
                    f"non-macOS entry left unchanged and unchecked (Platform={platform!r})",
                )
            )
            continue
        findings.extend(_evaluate_macos_app(index, app, manifest, repo_root))

    return findings


def load_manifest(path: Path) -> dict:
    try:
        import yaml
    except ImportError as error:
        raise MissingDependencyError(
            "PyYAML is required to load a manifest file (pip install pyyaml)"
        ) from error
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"manifest did not parse to a mapping: {path}")
    return data


def _print_findings(path: Path, findings: list[Finding], as_json: bool) -> None:
    if as_json:
        json.dump({"manifest": str(path), "findings": [f.to_json() for f in findings]}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return
    if not findings:
        print(f"{path}: no findings")
        return
    for finding in findings:
        print(f"{path}: [{finding.severity}] {finding.code} {finding.path}: {finding.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        required=True,
        metavar="PATH",
        help="path to a manifest YAML file; may be passed more than once",
    )
    parser.add_argument(
        "--repo-root",
        metavar="PATH",
        help="repository root used only to check an LOB Icon path exists (never to inspect a package)",
    )
    parser.add_argument("--json", action="store_true", help="emit findings as JSON instead of text")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    has_error = False

    for raw_path in args.manifest:
        path = Path(raw_path)
        try:
            manifest = load_manifest(path)
        except MissingDependencyError as error:
            print(f"{path}: {error}", file=sys.stderr)
            return 3
        except (OSError, ValueError) as error:
            print(f"{path}: cannot load manifest: {error}", file=sys.stderr)
            return 2

        try:
            findings = evaluate(manifest, repo_root=repo_root)
        except Exception as error:  # defensive: never crash without a path/reason
            print(f"{path}: internal error while evaluating manifest: {error}", file=sys.stderr)
            return 2

        _print_findings(path, findings, args.json)
        if any(f.severity == "error" for f in findings):
            has_error = True

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
