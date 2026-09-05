# macOS Manifest Contract

Use this reference when authoring or reviewing a macOS entry in a Relaypublisher
manifest. See [windows-manifest.md](windows-manifest.md) for the Windows Win32
counterpart; `Architecture`, `Requirements.MinimumOSVersion`, and the source-item
shape below are shared by both platforms. The target repository's schema and
validator remain authoritative if a future schema revision changes a field
outside this contract.

## Supported shape

The supported macOS installer is a PKG. The app entry must use:

```yaml
Platform: macos
Architecture: arm64       # or x64
InstallerType: pkg
AppType: pkg               # unmanaged macOS PKG app; often the default
# or: AppType: lob         # macOS LOB app
```

`InstallerType: dmg`, `AppType: dmg`, or a DMG source is unsupported. Do not model a
DMG as a PKG and do not add multiple independent `Source` values to represent files
inside one installer. A multi-bundle PKG still has one `Source`; its installed apps
are declared under `Detection.IncludedApps`.

The normal macOS entry has one PKG `Source`, `Requirements`, and `Detection`. `Source`
uses the same source-item shape as a Windows `Package.ExternalFiles` entry (`Type:
publicHttp | githubRelease | azureBlob`, a required 64-hex-char `Sha256`,
type-specific required fields, and `Auth` rules — see
[windows-manifest.md](windows-manifest.md#source-item-shape-shared-with-macos-source)
for the full table). Do not copy Windows-only `Package`, `Install`, or
`Detection.Type`/`Detection.ScriptFile` fields into a macOS entry.

## IncludedApps rules

`Detection.IncludedApps` describes application bundles that the PKG actually
installs. It is required for macOS and must contain between 1 and 500 entries.
Every entry requires:

| Manifest field | Source metadata | Rule |
|---|---|---|
| `BundleId` | `CFBundleIdentifier` | Required; duplicate detection uses ordinal, case-sensitive equality |
| `BundleVersion` | `CFBundleShortVersionString` | Required for every `pkg` and `lob` entry |

`IncludedApps[].BundleBuildVersion` does not exist in the `IncludedAppManifest`
model — it is not a valid manifest field for either `pkg` or `lob`. An entry
carrying it is rejected as an unsupported field, not mapped to any Graph
property. (`ManifestLoader` ignores unmatched YAML properties rather than
failing on them, so writing this field silently does nothing on a real
CLI run — the bundled checker exists in part to catch that silently-ignored
case before it reaches the CLI.)

The list is declarative. Never invent a bundle identifier or version, and do not
assume that the root `PackageVersion` is either bundle version field. If metadata is
unknown, ask for it or report that authoring is blocked.

Bundle IDs that differ only by case are distinct under this contract, although an
actual macOS bundle normally follows a stable lower-case convention. Keep the exact
spelling supplied by the authoritative metadata.

`Detection.IgnoreAppVersion` (optional, boolean, default `false`) excludes the
bundle version from Intune's installed-state detection (Graph
`ignoreVersionDetection`) when set to `true`. It has no interaction with which
entry is primary or with `IncludedApps` ordering.

## Primary bundle selection

There is no primary-bundle selector field. `IncludedApps[0]` is always the
primary entry — the first entry is also used for report display and, for
`AppType: pkg`, as the app's `primaryBundleId`/`primaryBundleVersion`. A
manifest that needs a different bundle to be primary must reorder
`IncludedApps` itself; there is no field that changes primary selection
without reordering the list.

`Detection.PrimaryBundleId` does not exist in this schema. Do not add it —
`ManifestLoader` ignores unmatched properties rather than failing on them, so
it would silently do nothing rather than select a primary bundle.

## PKG and LOB projection

The target Relaypublisher mapping uses `IncludedApps[0]` as follows:

| App type | Graph collection | Primary fields | Build/version fields |
|---|---|---|---|
| `pkg` | `includedApps` | `primaryBundleId`/`primaryBundleVersion` from `IncludedApps[0]` | not applicable — `pkg` has no build-number concept |
| `lob` | `childApps` | top-level `bundleId` from `IncludedApps[0]` | top-level `buildNumber` **and** `versionNumber`, and each `childApps[].buildNumber`/`versionNumber`, are all `BundleVersion` — there is no separate build-number field |

The payload projection reads `IncludedApps[0]` for the primary/top-level
fields. That is not a reason to reorder or normalize the source manifest —
reorder `IncludedApps` itself if a different entry must be primary.

`AppType: lob` also requires the root `Icon` according to the target schema. The
icon must satisfy that repository's path, format, size, and existence checks. Keep
those checks separate from bundle metadata authoring.

## Updaters and other bundled apps

List only bundles whose installation should participate in Intune detection. If a
PKG contains an independently updating helper or updater that should not gate
detection, omit it from `IncludedApps`. There is no updater exclude list in this
contract, and the skill must not invent an updater-name heuristic or silently add an
updater entry.

This means omission is intentional even when the package contains the updater. The
remaining listed apps must still be real bundles installed by the PKG; omission is
not permission to fabricate a substitute bundle.

## Pre/post-install Scripts (`AppType: pkg` only)

```yaml
Scripts:
  PreInstall: scripts/macos/contoso-tool/preinstall.sh   # optional
  PostInstall: scripts/macos/contoso-tool/postinstall.sh # optional
```

`Scripts` maps to the Graph `macOSPkgApp` resource's `preInstallScript`/
`postInstallScript` and only exists for `AppType: pkg`; `AppType: lob` and
every `Platform: windows` entry must not set it. When `Scripts` is present,
at least one of `PreInstall`/`PostInstall` is required (both null is
invalid). Each set value must be a repository-relative path with no
traversal segments or absolute-path prefix, and must have a `.sh` extension.

When the bundled checker is run with `--repo-root`, it additionally confirms
the script file exists, has no UTF-8 byte-order mark (a BOM before the
shebang stops macOS from launching the script at all), starts with a
shebang (`#!`), and stays under the target Graph resource's documented
15,360-character limit after CRLF/CR-to-LF normalization. Without
`--repo-root`, only the path shape and extension are checked — the same
shape-only/existence-gated split used for the root `Icon`.

Script contents are never included in any hash this checker computes (there
is none today); a script-only change does not require re-uploading the PKG.

## Assignments and Categories (shared with Windows)

`Assignments` and `Categories` use the identical shape on macOS and Windows
entries. See
[windows-manifest.md](windows-manifest.md#assignments-shared-with-macos) for
the full field tables, enum values, and duplicate/uniqueness rules. The one
macOS-specific rule: `AppType: pkg` (the default) forbids
`Assignments[].Intent: uninstall`; `AppType: lob` allows it.

## Static validation checklist

Review these invariants before invoking the CLI. The bundled checker
(`scripts/manifest_policy.py`) enforces items 0–8 automatically and reports each
violation under the listed `RP0xx` code; items 9–10 are authoring discipline the
checker cannot fully verify on its own.

0. `Platform` is `macos` (`RP013`); `Architecture` is `x64` or `arm64` and matches
   `Requirements.Architecture` when the latter is set (`RP014`, `RP016`);
   `Requirements.MinimumOSVersion` is non-empty (`RP015`).
1. `InstallerType` is `pkg` (`RP001`), with no Windows-only `Package`/`Install` fields
   or Windows-only `Detection` fields — `Type` and every script- or file-detection
   field (`ScriptFile`, `RunAs32Bit`, `EnforceSignatureCheck`, `Path`,
   `FileOrFolderName`, `OperationType`, `Operator`, `ComparisonValue`,
   `Check32BitOn64System`) — on the entry (`RP003`, `RP044`), and exactly one
   `Source` object (`RP003`) satisfying the shared source-item shape (`RP020`-`RP027`;
   see [windows-manifest.md](windows-manifest.md#source-item-shape-shared-with-macos-source)).
2. `AppType` is `pkg` or `lob` (or is omitted only where the target schema explicitly
   defines the default as `pkg`) (`RP002`).
3. The entry has one PKG `Source`, required `Requirements`, and `Detection` fields
   required by the target schema (`RP003`).
4. `IncludedApps` has 1–500 entries (`RP004`), no ordinal/case-sensitive duplicate
   `BundleId` (`RP006`), non-empty `BundleId`/`BundleVersion` values (`RP005`), and no
   fields outside `BundleId`/`BundleVersion` (`RP012`) — `BundleBuildVersion` does not
   exist in this schema and is rejected under the same code regardless of `AppType`.
5. `AppType: lob` requires a non-empty root `Icon` (`RP011`).
6. `Detection.PrimaryBundleId` does not exist in this schema. If present at all — blank,
   exact match, or not — it is rejected (`RP009`); `IncludedApps[0]` is always the
   primary entry. (Retired: `RP007`/`RP008`, the removed `BundleBuildVersion`
   required/forbidden checks; `RP010`, the removed selector-resolution check.)
7. `Scripts` (if present) is set only on `AppType: pkg`, sets at least one of
   `PreInstall`/`PostInstall`, uses a safe repository-relative `.sh` path, and
   (with `--repo-root`) exists, has no BOM, starts with a shebang, and stays
   under the character limit (`RP070`-`RP079`).
8. `Assignments`/`Categories` satisfy the shared rules in
   [windows-manifest.md](windows-manifest.md#assignments-shared-with-macos)
   (`RP050`-`RP062`), including the macOS `AppType: pkg` + `Intent: uninstall`
   restriction (`RP058`).
9. Updaters are omitted deliberately rather than represented by a new exclusion
   property.
10. The YAML order and unrelated fields remain unchanged.

Use the Relaypublisher CLI without packaging or publication:

```bash
relaypublisher validate --repo-root "$RELAYPUBLISHER_REPO" --manifest "$MANIFEST"
```

```powershell
relaypublisher validate --repo-root $RelaypublisherRepo --manifest $Manifest
```

`validate` is not a package-inspection command and should not download the source.
It may still check local assets referenced by the manifest. Do not add `--force`.

If a CLI is not installed, report validation as unavailable. If the CLI is older
than Relaypublisher v1.1.0 and a Windows entry in the same changeset uses
`Detection.Type: file`, report a version mismatch rather than downgrading that
entry to script-based detection to make an old command pass.

## Complete examples

The following are concise schema-valid shapes. Their Azure Blob names, checksum,
and (for LOB) icon path are illustrative: replace them with real values and an
existing icon before running repository validation. Both examples have one PKG
source and two declared bundles.

### Multi-bundle unmanaged PKG

```yaml
SchemaVersion: "1.0"
PackageIdentifier: Contoso.MultiBundle
PackageName: Contoso Multi Bundle
Publisher: Contoso Ltd.
Description: Multi-bundle macOS PKG example.
PackageVersion: "4.2.0"

Apps:
  - Platform: macos
    Architecture: arm64
    InstallerType: pkg
    AppType: pkg
    DisplayName: Contoso Multi Bundle [macOS Arm64]
    Source:
      Type: azureBlob
      AccountName: examplepackages
      Container: intune-packages
      BlobName: macos/contoso/4.2.0/Contoso.pkg
      Destination: Contoso.pkg
      Sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      Auth:
        Type: workloadIdentity
    Requirements:
      MinimumOSVersion: "13.0"
    Detection:
      IncludedApps:
        - BundleId: com.example.contoso.client
          BundleVersion: "4.2.0"
        - BundleId: com.example.contoso.helper
          BundleVersion: "4.2.0"
```

`com.example.contoso.client` is `IncludedApps[0]`, so it is the primary entry. An
updater that is present in the PKG but should not gate detection is intentionally
absent from this list.

### Multi-bundle macOS LOB

```yaml
SchemaVersion: "1.0"
PackageIdentifier: Contoso.MultiBundleLob
PackageName: Contoso Multi Bundle LOB
Publisher: Contoso Ltd.
Description: Multi-bundle macOS LOB example.
PackageVersion: "4.2.0"
Icon: icons/contoso.png

Apps:
  - Platform: macos
    Architecture: arm64
    InstallerType: pkg
    AppType: lob
    DisplayName: Contoso Multi Bundle LOB [macOS Arm64]
    Source:
      Type: azureBlob
      AccountName: examplepackages
      Container: intune-packages
      BlobName: macos/contoso-lob/4.2.0/ContosoLob.pkg
      Destination: ContosoLob.pkg
      Sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      Auth:
        Type: workloadIdentity
    Requirements:
      MinimumOSVersion: "13.0"
    Detection:
      IncludedApps:
        - BundleId: com.example.contoso.lob.main
          BundleVersion: "4.2.0"
        - BundleId: com.example.contoso.lob.helper
          BundleVersion: "4.2.0"
```

For the LOB example, `com.example.contoso.lob.main` is `IncludedApps[0]`, so its
`BundleVersion` populates both the top-level `buildNumber` and `versionNumber` (and
each `childApps[].buildNumber`/`versionNumber`) — there is no separate build-number
field to supply. The icon path must point to an existing supported image in the
target repository.

## Fixtures

`../tests/fixtures/` contains one manifest per checklist scenario above, used by
`../tests/test_manifest_policy.py`:

| Fixture | Checklist item(s) exercised |
|---|---|
| `valid-pkg-multibundle.yaml` | Full valid shape; the updater is intentionally omitted from `IncludedApps` (item 9) |
| `valid-lob-multibundle.yaml` | Full valid LOB shape, including root `Icon` (item 5) |
| `valid-macos-ignore-app-version.yaml` | `Detection.IgnoreAppVersion: true` on a `pkg` entry |
| `invalid-dmg.yaml` | Rejects `InstallerType: dmg` (`RP001`, item 1) |
| `invalid-macos-primary-bundle-id.yaml` | Rejects a present `Detection.PrimaryBundleId` (`RP009`, item 6) |
| `invalid-macos-bundle-build-version.yaml` | Rejects `IncludedApps[].BundleBuildVersion` as an unsupported field (`RP012`, item 4) |
| `invalid-duplicate-bundleid.yaml` | Rejects an ordinal, case-sensitive duplicate `BundleId` (`RP006`, item 4) |
| `invalid-unsupported-platform.yaml` | Rejects a `Platform` that is neither `macos` nor `windows` (`RP013`, item 0) |
| `valid-assignments-categories-scripts.yaml` | Valid `Scripts`/`Categories`/`Assignments` together on a macOS `pkg` entry (items 7, 8) |
| `invalid-assignment-duplicate-target.yaml` | Rejects two assignments resolving to the same target (`RP057`, item 8) |
| `invalid-categories-duplicate.yaml` | Rejects a case-insensitive duplicate category name (`RP062`, item 8) |
| `invalid-scripts-on-windows.yaml` | Rejects macOS-only `Scripts` set on a Windows entry (`RP070`, item 7) |

See [windows-manifest.md](windows-manifest.md#fixtures) for the Windows-side fixtures.
