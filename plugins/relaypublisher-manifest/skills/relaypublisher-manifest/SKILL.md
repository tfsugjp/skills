---
name: relaypublisher-manifest
description: 'Create, update, and statically validate Relaypublisher YAML manifests, including Windows Win32 manifests and macOS PKG/LOB manifests that declare multiple application bundles. Use when Win32 package/install/detection fields, macOS bundle detection, primary bundle selection, or other manifest fields need authoring or review. Do not use for packaging, publishing, force acknowledgements, Graph calls, or tenant changes.'
compatibility: 'Bundled checker (scripts/manifest_policy.py) requires Python 3.10+ and PyYAML (pip install pyyaml). Full validation additionally requires a Relaypublisher CLI or source revision new enough to understand the manifest fields in use — for macOS multi-bundle manifests specifically, Detection.PrimaryBundleId and IncludedApps[].BundleBuildVersion.'
---

# Relaypublisher Manifest

Use this skill for manifest-only work in a Relaypublisher repository, for both
the Windows Win32 and macOS PKG/LOB platforms. The goal is a small, reviewable
YAML change that describes the intended application metadata and passes the
target repository's schema validation. It does not build a `.intunewin` or PKG,
does not acquire or inspect a package, and does not change Intune state.

## Establish the target contract

Before editing a manifest:

1. Read the target repository's canonical manifest schema and relevant examples
   for the platform(s) involved. Prefer its current documentation and source
   model/validator over remembered Relaypublisher behavior. In the standard
   repository these are the manifest schema document and the manifest model,
   validation, bundle-selector, and platform-specific payload mapping code.
2. For a macOS multi-bundle manifest specifically, confirm the CLI version or
   source revision supports `Detection.PrimaryBundleId` and
   `IncludedApps[].BundleBuildVersion`. Run `relaypublisher --version` (or the
   target repository's equivalent) and check it against the repository's
   changelog for the revision that introduced those fields. A CLI that ignores
   those fields is not a compatible validator for this work.
3. Obtain every required value — bundle identifiers/versions, Win32 command
   lines, source checksums, and so on — from user-supplied or otherwise
   authoritative package metadata. Never guess a value (a bundle identifier, a
   `CFBundleShortVersionString`, a `CFBundleVersion`, a `Sha256`, an install
   command line), and never silently substitute an unrelated field (such as
   the root `PackageVersion`) for a missing one.

Read [Windows Win32 manifest contract](references/windows-manifest.md) or
[macOS manifest contract](references/macos-manifest.md) for the detailed rules,
field mapping, examples, and static-validation checklist for each platform.

## Scope and hard boundaries

- Author, update, and statically validate Relaypublisher manifests only, for
  the Windows Win32 and macOS PKG/LOB platforms. An app entry with any other
  `Platform` value is rejected, not silently accepted or ignored.
- For Windows, the source is Win32: use `InstallerType: win32` with a `Package`
  block (`IntuneWin.SetupFile`, optional `RepositoryFiles`/`ExternalFiles`).
  Never copy macOS-only `AppType` or `Source` fields onto a Windows entry.
- For macOS, the source is a PKG: use `InstallerType: pkg` and `AppType: pkg`
  or `AppType: lob`. DMG installers are unsupported; do not translate a DMG
  into a PKG manifest or add a guessed DMG schema. Never copy Windows-only
  `Package`, `Install`, or script-based `Detection` fields onto a macOS entry.
- A multi-bundle macOS manifest has one PKG source and an explicit
  `Detection.IncludedApps` list. It is not a manifest containing multiple
  independent package sources.
- Do not run `package` or `publish`, download/unpack/inspect installer or
  `.intunewin` contents, pass `--force`, call Microsoft Graph, or make
  tenant/app/assignment changes.
- Do not add an updater exclusion list or an automatic updater allow/deny
  heuristic. Omit an updater from macOS `IncludedApps` when it must not
  participate in detection.
- `Assignments` and `Categories` (shared by both platforms) and macOS
  pre/post-install `Scripts` may be authored and statically validated, but
  only the manifest fields — never call Microsoft Graph to resolve a category
  name against a tenant or to apply an assignment.

## Author or update a Windows Win32 manifest

1. Make the smallest change that satisfies the user's request. Preserve YAML
   key order, comments, formatting style, and unrelated fields.
2. Keep the existing root and platform fields intact unless the user asks to
   change them. Use `Platform: windows`, `Architecture: x64` or `arm64`, and
   `InstallerType: win32`. Do not set `AppType` or `Source` on this entry.
3. Build the `Package` block from known installer facts:
   - `IntuneWin.SetupFile` is required and must be the actual setup script's
     staging-relative path;
   - each `RepositoryFiles` entry needs a real repository-relative `Source`
     and staging-relative `Destination`;
   - each `ExternalFiles` entry needs a real source `Type`
     (`publicHttp`/`githubRelease`/`azureBlob`), its type-specific required
     fields, a real `Sha256` (never fabricate one), and correct `Auth` (token
     auth needs `SecretName`; `azureBlob` requires `workloadIdentity`;
     `githubRelease` forbids it).
4. Build `Install` from known behavior: real `CommandLine`/
   `UninstallCommandLine`, and an `InstallExperience`/`RestartBehavior` that
   matches how the installer actually behaves. Only add `ReturnCodes` when the
   installer's codes differ from Intune's default set — do not restate the
   default set just to make it explicit.
5. Set `Detection.Type: script` with the real detection script's path in
   `ScriptFile`. Windows has no other detection mechanism in this contract.
6. Set `Requirements.MinimumOSVersion` to the real minimum build, and
   `Requirements.Architecture` (if set) to match the app-level `Architecture`
   exactly.
7. If the user asks for `Assignments` or `Categories`, follow the shared rules
   in step 8 of "Author or update a macOS manifest" below — they are identical
   on Windows.

If required installer metadata is unavailable, stop with a clear request for
the exact values and leave the manifest unchanged.

## Author or update a macOS manifest

1. Make the smallest change that satisfies the user's request. Preserve YAML key and
   list order, comments, formatting style, and unrelated fields. Do not sort
   `IncludedApps`; primary-first ordering is a Graph-payload concern, not a manifest
   rewrite.
2. Keep the existing root and platform fields intact unless the user asks to change
   them. For each macOS entry, use one `Source` describing the PKG and keep Windows
   `Package`/`Install` fields out of the macOS entry.
3. Build `Detection.IncludedApps` from known installed application bundles:
   - include one to 500 entries;
   - use a non-empty `BundleId` and `BundleVersion` for every entry;
   - compare `BundleId` values with ordinal, case-sensitive equality when checking
     duplicates; and
   - map `BundleVersion` to `CFBundleShortVersionString`.
4. For `AppType: lob`, set `BundleBuildVersion` on every entry to the exact
   `CFBundleVersion` value. For `AppType: pkg`, omit `BundleBuildVersion`; it is not
   part of the PKG mapping. Do not create a value merely because a PKG has a build
   number.
5. If `Detection.PrimaryBundleId` is present, resolve it against the declared list
   with ordinal, case-sensitive matching. A match is either an exact `BundleId` or a
   `BundleId` beginning with `PrimaryBundleId + "."`. Exactly one entry must match;
   reject zero and ambiguous matches. If the selector is omitted, the first list
   entry remains primary. An empty or whitespace-only selector is invalid.
6. Do not list a bundled updater solely because it is present in the PKG. Exclusion is
   represented by omission from `IncludedApps`, never by an invented exclude field.
7. Preserve the manifest's declared order even when a non-first entry is selected as
   primary. Do not rewrite other entries around the selector.
8. If the user asks for `Assignments` (shared by both platforms): use a real
   Entra ID group GUID for `Target: group`, set no `GroupId` for
   `allDevices`/`allLicensedUsers`, set `Intent` for every `include`-mode entry
   (default), and never add `Intent: uninstall` to a macOS `AppType: pkg`
   entry — `AppType: lob` and Windows both allow it. Never add a second entry
   that resolves to the same `(Target, GroupId, Mode)` as an existing one. For
   `Categories` (also shared): use the tenant's real category display names
   verbatim (no trimming), keep them unique per entry (case-insensitive), and
   distinguish omitting `Categories` (leaves existing relationships alone)
   from `Categories: []` (clears all of them) — never emit an empty list only
   to make omission "explicit".
9. If the user asks for pre/post-install `Scripts` on an `AppType: pkg` entry:
   set at least one of `PreInstall`/`PostInstall` to the real script's
   repository-relative `.sh` path. Never set `Scripts` on `AppType: lob` or a
   Windows entry. Do not alter the referenced script's content — that is a
   separately authorized task, not manifest authoring.

If required bundle metadata is unavailable, stop with a clear request for the exact
values and leave the manifest unchanged. A syntactically valid but fabricated
`IncludedApps` entry is not a successful result.

## Static validation

Validation has two independent layers. Passing the first is not a substitute for the
second — report both separately and never claim Relaypublisher validation passed
because the bundled checker passed.

### 1. Bundled checker (always available)

Run the CLI-independent checker bundled with this skill against every changed
entry, Windows or macOS. It requires PyYAML (`pip install pyyaml`) and never
downloads a `Source`/`ExternalFiles` payload, inspects the PKG or `.intunewin`,
or touches the network:

```bash
python scripts/manifest_policy.py --manifest "$MANIFEST" --repo-root "$REPO_ROOT"
```

PowerShell 7 equivalent:

```powershell
python scripts\manifest_policy.py --manifest $Manifest --repo-root $RepoRoot
```

`--repo-root` is optional and only used to confirm a macOS `AppType: lob`
`Icon` path exists; omit it when no repository context is available. Exit code
`0` means no contract violation was found; `1` means at least one was; `3`
means PyYAML is not installed. Pass `--json` for machine-readable findings.
This checker is not the Relaypublisher schema authority — it only catches the
manifest-authoring mistakes this skill is responsible for (wrong installer
type per platform, malformed `Package`/`Install`/`Detection`/`IncludedApps`
blocks, ambiguous/unresolved macOS primary selectors, cross-platform field
misuse, source-item shape errors, and malformed `Assignments`/`Categories`/
macOS `Scripts`). It never resolves a `Categories` name against a tenant
catalog or applies an `Assignments` entry — those remain Graph-side concerns
outside this skill's boundary.

### 2. Relaypublisher CLI (when available)

Run the target CLI from the Relaypublisher repository root when it is available:

```bash
relaypublisher validate --repo-root "$RELAYPUBLISHER_REPO" --manifest "$MANIFEST"
```

PowerShell 7 equivalent:

```powershell
relaypublisher validate --repo-root $RelaypublisherRepo --manifest $Manifest
```

An existing manifest list may be validated instead:

```bash
relaypublisher validate --repo-root "$RELAYPUBLISHER_REPO" --manifest-list "$MANIFEST_LIST"
```

The validation run is static. It may validate repository-backed assets such as an
icon, but it must not download the `Source`/`ExternalFiles` payload or inspect the
PKG/`.intunewin`. Check the output for schema errors, per-platform installer-type
restrictions, `IncludedApps` count/duplicate errors, primary-selector errors, and
missing LOB build values. Do not claim Relaypublisher validation passed if the
command is unavailable.

When the CLI is unavailable, rely on the bundled checker plus a syntax and contract
review using the target repository's schema tooling if present, then report that
Relaypublisher validation is incomplete. When the CLI is too old or rejects the new
fields, report a version mismatch and retain `PrimaryBundleId` and
`BundleBuildVersion`; never delete or downgrade those fields to make an old command
pass.

Finish by reporting the changed manifest path(s), the metadata source, the
bundled-checker result, the Relaypublisher CLI command/result (or its unavailability),
and any validation limitation. Keep package, publish, Graph, and tenant work for a
separately authorized task.
