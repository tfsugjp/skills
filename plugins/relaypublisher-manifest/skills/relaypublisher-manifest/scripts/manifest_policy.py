#!/usr/bin/env python3
"""Statically check a Relaypublisher manifest against the Windows Win32 and macOS
PKG/LOB contracts.

This is a bundled, CLI-independent checker for the invariants documented in
``references/windows-manifest.md`` and ``references/macos-manifest.md``. It is
not the Relaypublisher schema validator and passing it is not equivalent to a
passing ``relaypublisher validate`` run: it only catches the manifest-authoring
mistakes this skill is responsible for (wrong installer type per platform,
malformed ``IncludedApps``/``Package``/``Install``/``Detection`` blocks —
including Windows script- and file-system detection rules — cross-platform
field misuse, and malformed ``Assignments``/``Categories``/macOS ``Scripts``
blocks). It never downloads, unpacks, or inspects a package or
``.intunewin``, and it never calls Microsoft Graph or changes tenant state —
Category names are never resolved against a tenant catalog.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

SUPPORTED_PLATFORMS = {"windows", "macos"}
SUPPORTED_ARCHITECTURES = {"x64", "arm64"}

SUPPORTED_APP_TYPES = {"pkg", "lob"}
DEFAULT_APP_TYPE = "pkg"
WINDOWS_ONLY_KEYS = ("Package", "Install")
# BundleBuildVersion does not exist in the v1.1.0 IncludedAppManifest model; an
# entry carrying it is rejected as an unsupported field (RP012), not silently
# mapped anywhere.
ALLOWED_INCLUDED_APP_KEYS = {"BundleId", "BundleVersion"}
MIN_INCLUDED_APPS = 1
MAX_INCLUDED_APPS = 500

SOURCE_TYPES = {"publicHttp", "githubRelease", "azureBlob"}
SOURCE_TYPE_REQUIRED_FIELDS = {
    "publicHttp": ("Url",),
    "githubRelease": ("Owner", "Repository", "Tag", "AssetName"),
    "azureBlob": ("AccountName", "Container", "BlobName"),
}
AUTH_TYPES = {"none", "token", "workloadIdentity"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

INSTALL_EXPERIENCES = {"system", "user"}
RESTART_BEHAVIORS = {"suppress", "allow", "force"}
RETURN_CODE_TYPES = {"success", "softReboot", "hardReboot", "retry", "failed"}
# "file" was added in Relaypublisher v1.1.0 (additive; SchemaVersion stays "1.0").
WINDOWS_DETECTION_TYPES = {"script", "file"}
FILE_OPERATION_TYPES = {"exists", "version"}
FILE_OPERATORS = {"equal", "notEqual", "greaterThan", "greaterThanOrEqual", "lessThan", "lessThanOrEqual"}
FILE_VERSION_RE = re.compile(r"^\d{1,5}(\.\d{1,5}){0,3}$")
# Mirrors ManifestValues.TargetDevicePathRootRegex: drive-rooted, root-relative,
# UNC, or environment-variable-rooted. Detection.Path/FileOrFolderName are
# evaluated on the target device, not resolved against --repo-root.
TARGET_DEVICE_PATH_ROOT_RE = re.compile(
    r"^[A-Za-z]:\\|^\\[^\\]|^\\\\[^\\]+\\[^\\]+(?:\\.*)?$|^%[A-Za-z_][A-Za-z0-9_()]*%\\"
)
SCRIPT_ONLY_DETECTION_KEYS = ("ScriptFile", "RunAs32Bit", "EnforceSignatureCheck")
FILE_ONLY_DETECTION_KEYS = ("Path", "FileOrFolderName", "OperationType", "Operator", "ComparisonValue", "Check32BitOn64System")

ASSIGNMENT_TARGETS = {"group", "allDevices", "allLicensedUsers"}
DEFAULT_ASSIGNMENT_TARGET = "group"
ASSIGNMENT_MODES = {"include", "exclude"}
DEFAULT_ASSIGNMENT_MODE = "include"
ASSIGNMENT_INTENTS = {"required", "available", "uninstall"}
FILTER_MODES = {"include", "exclude"}
NOTIFICATION_VALUES = {"showAll", "showReboot", "hideAll"}

MACOS_SCRIPT_EXTENSION = ".sh"
MAX_MACOS_SCRIPT_CHARS = 15360
MAX_MACOS_SCRIPT_BYTES = MAX_MACOS_SCRIPT_CHARS * 4 + 3
UTF8_BOM = b"\xef\xbb\xbf"


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


def _is_valid_guid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


_DRIVE_LETTER_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def _is_safe_relative_path(value: Any) -> bool:
    """Mirror Relaypublisher's PathSafety.IsSafeRelativePath: non-blank, not absolute
    (checked against both POSIX and Windows conventions, since a manifest may be
    authored on either OS), and no ".." traversal segment.

    A drive-relative Windows path like "C:foo" (no separator after the colon) is
    checked explicitly: PureWindowsPath("C:foo").is_absolute() is False, but .NET's
    Path.IsPathRooted("C:foo") — what PathSafety.cs actually calls — is True, so a
    bare .is_absolute() check alone would let it through.
    """
    if not _is_nonblank_str(value):
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    if _DRIVE_LETTER_PREFIX_RE.match(value):
        return False
    if PureWindowsPath(value).is_absolute():
        return False
    if ".." in re.split(r"[/\\]", value):
        return False
    return True


def _resolve_within_repo_root(repo_root: Path, relative_path: str) -> Path | None:
    """Resolve `relative_path` under `repo_root`, following symlinks, and confirm the
    result still stays inside the root — mirroring PathSafety.ResolveWithin. Returns
    None when it escapes (e.g. a symlink inside the repo pointing outside it), so the
    caller never treats an out-of-root file as a validated manifest asset."""
    root_resolved = repo_root.resolve()
    candidate = (root_resolved / relative_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    return candidate


_INVALID_TARGET_DEVICE_CHARS = set('*?<>"|/')


def _has_invalid_target_device_text(value: str) -> bool:
    if not _is_nonblank_str(value):
        return True
    if value != value.strip():
        return True
    if any(char in _INVALID_TARGET_DEVICE_CHARS for char in value):
        return True
    if any(unicodedata.category(char) == "Cc" for char in value):
        return True
    return False


def _has_traversal_segment(value: str) -> bool:
    return any(segment in (".", "..") for segment in value.split("\\"))


def _has_valid_target_device_path_colon_placement(value: str) -> bool:
    colon_index = value.find(":")
    if colon_index < 0:
        return True
    return colon_index == 1 and value.count(":") == 1


def _is_valid_target_device_path(value: str) -> bool:
    """Mirror ManifestValues.IsValidTargetDevicePath: `value` is evaluated on the
    target Windows device, so drive-rooted, root-relative, UNC, and
    environment-variable-rooted paths are all valid — it is never treated as a
    repository-relative path."""
    return (
        not _has_invalid_target_device_text(value)
        and TARGET_DEVICE_PATH_ROOT_RE.match(value) is not None
        and _has_valid_target_device_path_colon_placement(value)
        and not _has_traversal_segment(value)
    )


def _is_valid_target_device_leaf_name(value: str) -> bool:
    """Mirror ManifestValues.IsValidTargetDeviceLeafName: exactly one target-device
    leaf name, with no directory separator, drive letter, or `.`/`..` segment."""
    return (
        not _has_invalid_target_device_text(value)
        and "\\" not in value
        and "/" not in value
        and value not in (".", "..")
        and ":" not in value
    )


def _evaluate_source_item(path: str, source: Any) -> list[Finding]:
    """Check one source-provider item: macOS `Source` or one Windows `ExternalFiles[i]`.

    Both use the same shape (RP020-RP027), matching Relaypublisher's shared
    SourceManifest model: Type-specific required fields, a 64-hex-char Sha256,
    and Auth rules (token requires SecretName; azureBlob requires
    workloadIdentity; githubRelease forbids workloadIdentity).
    """
    findings: list[Finding] = []
    if not isinstance(source, dict):
        findings.append(_finding("RP020", "error", path, "source item must be a mapping"))
        return findings

    source_type = source.get("Type")
    if source_type not in SOURCE_TYPES:
        findings.append(
            _finding("RP020", "error", f"{path}.Type", f"unsupported source Type (must be one of {sorted(SOURCE_TYPES)}): {source_type!r}")
        )

    if not _is_nonblank_str(source.get("Destination")):
        findings.append(_finding("RP021", "error", f"{path}.Destination", "Destination is required and must be non-empty"))

    sha256 = source.get("Sha256")
    if not (_is_nonblank_str(sha256) and SHA256_RE.fullmatch(sha256.strip())):
        findings.append(_finding("RP022", "error", f"{path}.Sha256", "Sha256 must be a 64 character hexadecimal string"))

    for field in SOURCE_TYPE_REQUIRED_FIELDS.get(source_type, ()):
        if not _is_nonblank_str(source.get(field)):
            findings.append(
                _finding("RP023", "error", f"{path}.{field}", f"{field} is required for source Type {source_type!r}")
            )

    auth = source.get("Auth")
    auth_type = auth.get("Type") if isinstance(auth, dict) else None
    if auth is not None:
        if not isinstance(auth, dict):
            findings.append(_finding("RP024", "error", f"{path}.Auth", "Auth must be a mapping"))
        elif auth_type is not None and auth_type not in AUTH_TYPES:
            findings.append(
                _finding("RP024", "error", f"{path}.Auth.Type", f"unsupported Auth.Type (must be one of {sorted(AUTH_TYPES)}): {auth_type!r}")
            )
        if auth_type == "token" and not _is_nonblank_str(auth.get("SecretName")):
            findings.append(
                _finding("RP025", "error", f"{path}.Auth.SecretName", "Auth.SecretName is required when Auth.Type is 'token'")
            )
        if source_type == "githubRelease" and auth_type == "workloadIdentity":
            findings.append(
                _finding(
                    "RP026",
                    "error",
                    f"{path}.Auth.Type",
                    "Auth.Type 'workloadIdentity' is not supported for source Type 'githubRelease'; use 'token' or 'none'",
                )
            )

    if source_type == "azureBlob" and auth_type != "workloadIdentity":
        findings.append(
            _finding(
                "RP027",
                "error",
                f"{path}.Auth.Type",
                "Auth.Type must be 'workloadIdentity' for source Type 'azureBlob'",
            )
        )

    return findings


def _evaluate_common_app(index: int, app: dict) -> list[Finding]:
    """Checks that apply to every recognized-platform entry: RP014-RP016."""
    app_path = f"Apps[{index}]"
    findings: list[Finding] = []

    architecture = app.get("Architecture")
    if architecture not in SUPPORTED_ARCHITECTURES:
        findings.append(
            _finding(
                "RP014",
                "error",
                f"{app_path}.Architecture",
                f"unsupported Architecture (must be one of {sorted(SUPPORTED_ARCHITECTURES)}): {architecture!r}",
            )
        )

    requirements = app.get("Requirements")
    if not isinstance(requirements, dict) or not _is_nonblank_str(requirements.get("MinimumOSVersion")):
        findings.append(
            _finding("RP015", "error", f"{app_path}.Requirements.MinimumOSVersion", "Requirements.MinimumOSVersion is required and must be non-empty")
        )
    elif "Architecture" in requirements and requirements.get("Architecture") is not None:
        requirements_architecture = requirements.get("Architecture")
        if requirements_architecture != architecture:
            findings.append(
                _finding(
                    "RP016",
                    "error",
                    f"{app_path}.Requirements.Architecture",
                    f"Requirements.Architecture {requirements_architecture!r} must match the app Architecture {architecture!r}",
                )
            )

    return findings


def _evaluate_assignments(app_path: str, assignments: Any, is_macos_pkg: bool) -> list[Finding]:
    """RP050-RP058: the `Assignments` block, shared by Windows and macOS entries."""
    findings: list[Finding] = []
    if assignments is None:
        return findings
    if not isinstance(assignments, list):
        findings.append(_finding("RP050", "error", f"{app_path}.Assignments", "Assignments must be a list"))
        return findings

    seen_keys: set[str] = set()
    for i, entry in enumerate(assignments):
        entry_path = f"{app_path}.Assignments[{i}]"
        if not isinstance(entry, dict):
            findings.append(_finding("RP050", "error", entry_path, "entry must be a mapping"))
            continue

        target = entry.get("Target")
        if target is not None and target not in ASSIGNMENT_TARGETS:
            findings.append(
                _finding(
                    "RP050",
                    "error",
                    f"{entry_path}.Target",
                    f"unsupported Target (must be one of {sorted(ASSIGNMENT_TARGETS)}): {target!r}",
                )
            )
        effective_target = target if target in ASSIGNMENT_TARGETS else DEFAULT_ASSIGNMENT_TARGET

        group_id = entry.get("GroupId")
        if effective_target == "group":
            if not _is_valid_guid(group_id):
                findings.append(
                    _finding("RP051", "error", f"{entry_path}.GroupId", f"GroupId must be a valid GUID for Target 'group': {group_id!r}")
                )
        elif group_id is not None:
            findings.append(
                _finding("RP051", "error", f"{entry_path}.GroupId", f"GroupId must not be set when Target is {effective_target!r}")
            )

        mode = entry.get("Mode")
        if mode is not None and mode not in ASSIGNMENT_MODES:
            findings.append(
                _finding("RP052", "error", f"{entry_path}.Mode", f"unsupported Mode (must be one of {sorted(ASSIGNMENT_MODES)}): {mode!r}")
            )
        effective_mode = mode if mode in ASSIGNMENT_MODES else DEFAULT_ASSIGNMENT_MODE

        intent = entry.get("Intent")
        if effective_mode == "include" and not _is_nonblank_str(intent):
            findings.append(_finding("RP053", "error", f"{entry_path}.Intent", "Intent is required for include assignments"))
        elif intent is not None and intent not in ASSIGNMENT_INTENTS:
            findings.append(
                _finding("RP053", "error", f"{entry_path}.Intent", f"unsupported Intent (must be one of {sorted(ASSIGNMENT_INTENTS)}): {intent!r}")
            )

        filter_id = entry.get("FilterId")
        if filter_id is not None and not _is_valid_guid(filter_id):
            findings.append(_finding("RP054", "error", f"{entry_path}.FilterId", f"FilterId must be a valid GUID: {filter_id!r}"))

        filter_mode = entry.get("FilterMode")
        if filter_id is not None and filter_mode not in FILTER_MODES:
            findings.append(
                _finding(
                    "RP055",
                    "error",
                    f"{entry_path}.FilterMode",
                    f"FilterMode ('include' or 'exclude') is required when FilterId is set: {filter_mode!r}",
                )
            )

        settings = entry.get("Settings")
        if isinstance(settings, dict):
            notifications = settings.get("Notifications")
            if notifications is not None and notifications not in NOTIFICATION_VALUES:
                findings.append(
                    _finding(
                        "RP056",
                        "error",
                        f"{entry_path}.Settings.Notifications",
                        f"unsupported Notifications (must be one of {sorted(NOTIFICATION_VALUES)}): {notifications!r}",
                    )
                )

        key = f"{effective_target}|{group_id.lower() if isinstance(group_id, str) else group_id}|{effective_mode}"
        if key in seen_keys:
            findings.append(_finding("RP057", "error", entry_path, f"duplicate assignment target: {key}"))
        seen_keys.add(key)

        if is_macos_pkg and intent == "uninstall":
            findings.append(
                _finding("RP058", "error", f"{entry_path}.Intent", "Intent 'uninstall' is not supported for macOS AppType 'pkg' apps")
            )

    return findings


def _evaluate_categories(app_path: str, categories: Any) -> list[Finding]:
    """RP060-RP062: the `Categories` field, shared by Windows and macOS entries.

    Category names are matched verbatim against the tenant catalog at publish
    time; that resolution is a Graph preflight concern and out of scope here.
    Omitting `Categories` entirely (None) is intentionally left unflagged and
    unprocessed: it means "leave existing app-category relationships
    untouched", which is different from `Categories: []` ("clear all").
    """
    findings: list[Finding] = []
    if categories is None:
        return findings
    if not isinstance(categories, list):
        findings.append(_finding("RP060", "error", f"{app_path}.Categories", "Categories must be a list"))
        return findings

    seen_lower: set[str] = set()
    for i, name in enumerate(categories):
        entry_path = f"{app_path}.Categories[{i}]"
        if not _is_nonblank_str(name):
            findings.append(_finding("RP060", "error", entry_path, "Categories entries must not be empty or whitespace-only"))
            continue
        if name != name.strip():
            findings.append(_finding("RP061", "error", entry_path, f"Categories entry must not have leading/trailing whitespace: {name!r}"))
        lowered = name.lower()
        if lowered in seen_lower:
            findings.append(_finding("RP062", "error", entry_path, f"duplicate Categories name (case-insensitive): {name!r}"))
        seen_lower.add(lowered)

    return findings


def _evaluate_macos_scripts(app_path: str, platform: str, app_type: str, scripts: Any, repo_root: Path | None) -> list[Finding]:
    """RP070-RP079: the macOS `Scripts` (pre/post-install) block, `AppType: pkg` only."""
    findings: list[Finding] = []
    if scripts is None:
        return findings

    if platform == "windows" or app_type == "lob":
        findings.append(
            _finding(
                "RP070",
                "error",
                f"{app_path}.Scripts",
                "Scripts must not be set for Platform 'windows' or macOS AppType 'lob'; pre/post-install scripts are only supported for AppType 'pkg'",
            )
        )
        return findings

    if not isinstance(scripts, dict):
        findings.append(_finding("RP070", "error", f"{app_path}.Scripts", "Scripts must be a mapping"))
        return findings

    pre_install = scripts.get("PreInstall")
    post_install = scripts.get("PostInstall")
    if pre_install is None and post_install is None:
        findings.append(_finding("RP071", "error", f"{app_path}.Scripts", "Scripts must set at least one of PreInstall or PostInstall"))

    for field, value in (("PreInstall", pre_install), ("PostInstall", post_install)):
        if value is None:
            continue
        field_path = f"{app_path}.Scripts.{field}"
        if not _is_safe_relative_path(value):
            findings.append(
                _finding("RP072", "error", field_path, f"{field} must be a repository-relative path without traversal segments: {value!r}")
            )
            continue
        if Path(value).suffix.lower() != MACOS_SCRIPT_EXTENSION:
            findings.append(_finding("RP073", "error", field_path, f"{field} must have the '{MACOS_SCRIPT_EXTENSION}' extension: {value!r}"))
            continue
        if repo_root is not None:
            findings.extend(_evaluate_macos_script_file(field_path, field, value, repo_root))

    return findings


def _evaluate_macos_script_file(field_path: str, field: str, relative_path: str, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    full_path = _resolve_within_repo_root(repo_root, relative_path)
    if full_path is None:
        findings.append(
            _finding(
                "RP074",
                "error",
                field_path,
                f"{field} '{relative_path}' resolves outside the repository root (after following symlinks)",
            )
        )
        return findings
    if not full_path.is_file():
        findings.append(_finding("RP074", "error", field_path, f"{field} '{relative_path}' does not exist under the repository root"))
        return findings

    size = full_path.stat().st_size
    if size > MAX_MACOS_SCRIPT_BYTES:
        findings.append(
            _finding(
                "RP076",
                "error",
                field_path,
                f"{field} '{relative_path}' is {size} bytes, exceeding the maximum of {MAX_MACOS_SCRIPT_BYTES} bytes",
            )
        )
        return findings

    raw = full_path.read_bytes()
    has_bom = raw.startswith(UTF8_BOM)
    if has_bom:
        findings.append(_finding("RP075", "error", field_path, f"{field} '{relative_path}' must not have a UTF-8 byte order mark (BOM)"))

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        findings.append(_finding("RP079", "error", field_path, f"{field} '{relative_path}' must be valid UTF-8 without invalid byte sequences"))
        return findings

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) >= MAX_MACOS_SCRIPT_CHARS:
        findings.append(
            _finding(
                "RP077",
                "error",
                field_path,
                f"{field} '{relative_path}' is {len(normalized)} characters, meeting or exceeding the maximum of {MAX_MACOS_SCRIPT_CHARS}",
            )
        )

    text_after_bom = normalized[1:] if has_bom and normalized.startswith("﻿") else normalized
    if not text_after_bom.startswith("#!"):
        findings.append(_finding("RP078", "error", field_path, f"{field} '{relative_path}' must start with a shebang ('#!')"))

    return findings


def _evaluate_included_apps(
    app_path: str,
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

    return findings, bundle_ids


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
    else:
        findings.extend(_evaluate_source_item(f"{app_path}.Source", source))

    detection = app.get("Detection")
    if not isinstance(detection, dict):
        findings.append(_finding("RP004", "error", f"{app_path}.Detection", "Detection is required for a macOS entry"))
    else:
        windows_only_detection_keys = sorted(
            key for key in ("Type", "ScriptFile", *FILE_ONLY_DETECTION_KEYS) if detection.get(key) is not None
        )
        if windows_only_detection_keys:
            findings.append(
                _finding(
                    "RP044",
                    "error",
                    f"{app_path}.Detection",
                    f"Windows-only Detection field(s) {windows_only_detection_keys} must not be set for a macOS entry",
                )
            )
        if "PrimaryBundleId" in detection:
            findings.append(
                _finding(
                    "RP009",
                    "error",
                    f"{app_path}.Detection.PrimaryBundleId",
                    "PrimaryBundleId does not exist in the v1.1.0 manifest schema; IncludedApps[0] is always "
                    "the primary entry and ManifestLoader silently ignores this field rather than failing on it",
                )
            )
        included_findings, _bundle_ids = _evaluate_included_apps(app_path, detection.get("IncludedApps"))
        findings.extend(included_findings)

    if app_type == "lob" and not _is_nonblank_str(root.get("Icon")):
        findings.append(_finding("RP011", "error", "Icon", "AppType: lob requires a non-empty root Icon path"))
    elif app_type == "lob" and repo_root is not None:
        icon_path = _resolve_within_repo_root(repo_root, root["Icon"])
        if icon_path is None:
            findings.append(
                _finding("RP011", "error", "Icon", f"Icon path resolves outside the repository root (after following symlinks): {root['Icon']}")
            )
        elif not icon_path.is_file():
            findings.append(_finding("RP011", "error", "Icon", f"Icon path does not exist under repo root: {root['Icon']}"))

    findings.extend(_evaluate_assignments(app_path, app.get("Assignments"), is_macos_pkg=(app_type == "pkg")))
    findings.extend(_evaluate_categories(app_path, app.get("Categories")))
    findings.extend(_evaluate_macos_scripts(app_path, "macos", app_type, app.get("Scripts"), repo_root))

    return findings


def _evaluate_windows_package(app_path: str, package: Any) -> list[Finding]:
    findings: list[Finding] = []
    package_path = f"{app_path}.Package"
    if not isinstance(package, dict):
        findings.append(_finding("RP032", "error", package_path, "Package is required for Platform 'windows'"))
        return findings

    intune_win = package.get("IntuneWin")
    if not isinstance(intune_win, dict) or not _is_nonblank_str(intune_win.get("SetupFile")):
        findings.append(
            _finding("RP033", "error", f"{package_path}.IntuneWin.SetupFile", "IntuneWin.SetupFile is required and must be non-empty")
        )

    repository_files = package.get("RepositoryFiles") or []
    if isinstance(repository_files, list):
        for i, entry in enumerate(repository_files):
            entry_path = f"{package_path}.RepositoryFiles[{i}]"
            if not isinstance(entry, dict) or not _is_nonblank_str(entry.get("Source")) or not _is_nonblank_str(entry.get("Destination")):
                findings.append(_finding("RP034", "error", entry_path, "RepositoryFiles entry requires non-empty Source and Destination"))
    else:
        findings.append(_finding("RP034", "error", f"{package_path}.RepositoryFiles", "RepositoryFiles must be a list"))

    external_files = package.get("ExternalFiles") or []
    if isinstance(external_files, list):
        for i, entry in enumerate(external_files):
            findings.extend(_evaluate_source_item(f"{package_path}.ExternalFiles[{i}]", entry))
    else:
        findings.append(_finding("RP020", "error", f"{package_path}.ExternalFiles", "ExternalFiles must be a list"))

    return findings


def _evaluate_windows_install(app_path: str, install: Any) -> list[Finding]:
    findings: list[Finding] = []
    install_path = f"{app_path}.Install"
    if not isinstance(install, dict):
        findings.append(_finding("RP035", "error", install_path, "Install is required for Platform 'windows'"))
        return findings

    if not _is_nonblank_str(install.get("CommandLine")):
        findings.append(_finding("RP036", "error", f"{install_path}.CommandLine", "CommandLine is required and must be non-empty"))
    if not _is_nonblank_str(install.get("UninstallCommandLine")):
        findings.append(_finding("RP036", "error", f"{install_path}.UninstallCommandLine", "UninstallCommandLine is required and must be non-empty"))

    install_experience = install.get("InstallExperience")
    if install_experience not in INSTALL_EXPERIENCES:
        findings.append(
            _finding(
                "RP037",
                "error",
                f"{install_path}.InstallExperience",
                f"unsupported InstallExperience (must be one of {sorted(INSTALL_EXPERIENCES)}): {install_experience!r}",
            )
        )

    restart_behavior = install.get("RestartBehavior")
    if restart_behavior not in RESTART_BEHAVIORS:
        findings.append(
            _finding(
                "RP038",
                "error",
                f"{install_path}.RestartBehavior",
                f"unsupported RestartBehavior (must be one of {sorted(RESTART_BEHAVIORS)}): {restart_behavior!r}",
            )
        )

    return_codes = install.get("ReturnCodes")
    if return_codes is not None:
        if isinstance(return_codes, list):
            for i, entry in enumerate(return_codes):
                entry_type = entry.get("Type") if isinstance(entry, dict) else None
                if entry_type not in RETURN_CODE_TYPES:
                    findings.append(
                        _finding(
                            "RP039",
                            "error",
                            f"{install_path}.ReturnCodes[{i}].Type",
                            f"unsupported ReturnCodes Type (must be one of {sorted(RETURN_CODE_TYPES)}): {entry_type!r}",
                        )
                    )
        else:
            findings.append(_finding("RP039", "error", f"{install_path}.ReturnCodes", "ReturnCodes must be a list"))

    return findings


def _evaluate_windows_detection(app_path: str, detection: Any) -> list[Finding]:
    findings: list[Finding] = []
    detection_path = f"{app_path}.Detection"
    if not isinstance(detection, dict):
        findings.append(_finding("RP040", "error", detection_path, "Detection is required for Platform 'windows'"))
        return findings

    detection_type = detection.get("Type")
    if detection_type not in WINDOWS_DETECTION_TYPES:
        findings.append(
            _finding(
                "RP040",
                "error",
                f"{detection_path}.Type",
                f"unsupported Detection.Type (must be one of {sorted(WINDOWS_DETECTION_TYPES)}): {detection_type!r}",
            )
        )
        return findings

    if detection_type == "script":
        findings.extend(_evaluate_windows_script_detection(detection_path, detection))
    else:
        findings.extend(_evaluate_windows_file_detection(detection_path, detection))

    return findings


def _evaluate_windows_script_detection(detection_path: str, detection: dict) -> list[Finding]:
    """RP041/RP049: `Detection.Type: script`. File-detection fields are mutually
    exclusive with a detection script (ManifestValidator.DetectionManifestValidator)."""
    findings: list[Finding] = []

    if not _is_nonblank_str(detection.get("ScriptFile")):
        findings.append(
            _finding("RP041", "error", f"{detection_path}.ScriptFile", "Detection.ScriptFile is required when Detection.Type is 'script'")
        )

    file_only_keys_present = sorted(key for key in FILE_ONLY_DETECTION_KEYS if detection.get(key) is not None)
    if file_only_keys_present:
        findings.append(
            _finding(
                "RP049",
                "error",
                detection_path,
                f"file-detection field(s) {file_only_keys_present} must not be set when Detection.Type is 'script'",
            )
        )

    return findings


def _evaluate_windows_file_detection(detection_path: str, detection: dict) -> list[Finding]:
    """RP042/RP043/RP045-RP049: `Detection.Type: file`, added in Relaypublisher
    v1.1.0 (doc/01-manifest-schema.md §5.2.1). Detects a file or folder on the
    target device without a detection script."""
    findings: list[Finding] = []

    script_only_keys_present = sorted(key for key in SCRIPT_ONLY_DETECTION_KEYS if detection.get(key) is not None)
    if script_only_keys_present:
        findings.append(
            _finding(
                "RP048",
                "error",
                detection_path,
                f"script-detection field(s) {script_only_keys_present} must not be set when Detection.Type is 'file'",
            )
        )

    path = detection.get("Path")
    if not _is_nonblank_str(path):
        findings.append(_finding("RP042", "error", f"{detection_path}.Path", "Detection.Path is required when Detection.Type is 'file'"))
    elif not _is_valid_target_device_path(path):
        findings.append(
            _finding(
                "RP042",
                "error",
                f"{detection_path}.Path",
                "Detection.Path must be a non-wildcard target-device drive-rooted, root-relative, UNC, or "
                f"environment-variable-rooted path without traversal segments: {path!r}",
            )
        )

    file_or_folder_name = detection.get("FileOrFolderName")
    if not _is_nonblank_str(file_or_folder_name):
        findings.append(
            _finding(
                "RP043",
                "error",
                f"{detection_path}.FileOrFolderName",
                "Detection.FileOrFolderName is required when Detection.Type is 'file'",
            )
        )
    elif not _is_valid_target_device_leaf_name(file_or_folder_name):
        findings.append(
            _finding(
                "RP043",
                "error",
                f"{detection_path}.FileOrFolderName",
                f"Detection.FileOrFolderName must be a single non-wildcard target-device leaf name: {file_or_folder_name!r}",
            )
        )

    operation_type = detection.get("OperationType")
    if not _is_nonblank_str(operation_type) or operation_type not in FILE_OPERATION_TYPES:
        findings.append(
            _finding(
                "RP045",
                "error",
                f"{detection_path}.OperationType",
                f"Detection.OperationType is required and must be one of {sorted(FILE_OPERATION_TYPES)} when "
                f"Detection.Type is 'file'. 'notConfigured' is a Graph unset sentinel and is not valid manifest "
                f"input: {operation_type!r}",
            )
        )
        return findings

    operator = detection.get("Operator")
    comparison_value = detection.get("ComparisonValue")

    if operation_type == "exists":
        if operator is not None:
            findings.append(
                _finding(
                    "RP046",
                    "error",
                    f"{detection_path}.Operator",
                    "Detection.Operator must not be set when Detection.OperationType is 'exists'",
                )
            )
        if comparison_value is not None:
            findings.append(
                _finding(
                    "RP047",
                    "error",
                    f"{detection_path}.ComparisonValue",
                    "Detection.ComparisonValue must not be set when Detection.OperationType is 'exists'",
                )
            )
    else:  # "version"
        if not _is_nonblank_str(operator) or operator not in FILE_OPERATORS:
            findings.append(
                _finding(
                    "RP046",
                    "error",
                    f"{detection_path}.Operator",
                    f"Detection.Operator is required and must be one of {sorted(FILE_OPERATORS)} when "
                    f"Detection.OperationType is 'version'. 'notConfigured' is a Graph unset sentinel and is not "
                    f"valid manifest input: {operator!r}",
                )
            )
        if not _is_nonblank_str(comparison_value):
            findings.append(
                _finding(
                    "RP047",
                    "error",
                    f"{detection_path}.ComparisonValue",
                    "Detection.ComparisonValue is required when Detection.OperationType is 'version'",
                )
            )
        elif not FILE_VERSION_RE.fullmatch(comparison_value.strip()):
            findings.append(
                _finding(
                    "RP047",
                    "error",
                    f"{detection_path}.ComparisonValue",
                    "Detection.ComparisonValue must be a numeric version with one to four parts of one to five "
                    f"digits each: {comparison_value!r}",
                )
            )

    return findings


def _evaluate_windows_app(index: int, app: dict) -> list[Finding]:
    app_path = f"Apps[{index}]"
    findings: list[Finding] = []

    installer_type = app.get("InstallerType")
    if installer_type != "win32":
        findings.append(
            _finding(
                "RP029",
                "error",
                f"{app_path}.InstallerType",
                f"unsupported Windows InstallerType (only win32 is supported): {installer_type!r}",
            )
        )

    if "AppType" in app and app.get("AppType") is not None:
        findings.append(
            _finding("RP030", "error", f"{app_path}.AppType", "AppType must not be set for Platform 'windows'; it only applies to macOS")
        )

    if "Source" in app and app.get("Source") is not None:
        findings.append(
            _finding("RP031", "error", f"{app_path}.Source", "Source must not be set for Platform 'windows'; use Package instead")
        )

    findings.extend(_evaluate_windows_package(app_path, app.get("Package")))
    findings.extend(_evaluate_windows_install(app_path, app.get("Install")))
    findings.extend(_evaluate_windows_detection(app_path, app.get("Detection")))
    findings.extend(_evaluate_assignments(app_path, app.get("Assignments"), is_macos_pkg=False))
    findings.extend(_evaluate_categories(app_path, app.get("Categories")))
    findings.extend(_evaluate_macos_scripts(app_path, "windows", None, app.get("Scripts"), None))

    return findings


def evaluate(manifest: dict, repo_root: Path | None = None) -> list[Finding]:
    """Check `manifest` (a parsed dict) against the Windows Win32 and macOS
    PKG/LOB contracts.

    Pure function: does not touch YAML parsing, the filesystem (unless
    `repo_root` is given, to check an LOB Icon's existence), or the network.
    An app entry with a `Platform` other than `windows` or `macos` is rejected
    (RP013) rather than silently skipped, since Relaypublisher itself only
    recognizes those two platform values.
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
        if platform not in SUPPORTED_PLATFORMS:
            findings.append(
                _finding(
                    "RP013",
                    "error",
                    f"{app_path}.Platform",
                    f"unsupported Platform (must be one of {sorted(SUPPORTED_PLATFORMS)}): {platform!r}",
                )
            )
            continue

        findings.extend(_evaluate_common_app(index, app))
        if platform == "macos":
            findings.extend(_evaluate_macos_app(index, app, manifest, repo_root))
        else:
            findings.extend(_evaluate_windows_app(index, app))

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
