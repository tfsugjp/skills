# macOS Manifest Contract

Use this reference when authoring or reviewing a macOS entry in a Relaypublisher
manifest. The target repository's schema and validator remain authoritative if a
future schema revision changes a field outside this contract.

## Supported shape

The supported macOS installer is a PKG. The app entry must use:

```yaml
Platform: macos
Architecture: arm64       # or x64, as supported by the target repository
InstallerType: pkg
AppType: pkg               # unmanaged macOS PKG app; often the default
# or: AppType: lob         # macOS LOB app
```

`InstallerType: dmg`, `AppType: dmg`, or a DMG source is unsupported. Do not model a
DMG as a PKG and do not add multiple independent `Source` values to represent files
inside one installer. A multi-bundle PKG still has one `Source`; its installed apps
are declared under `Detection.IncludedApps`.

The normal macOS entry has one PKG `Source`, `Requirements`, and `Detection`. Use the
target repository's required source-provider fields and checksum rules. Do not copy
Windows-only `Package` or `Install` blocks into a macOS entry.

## IncludedApps rules

`Detection.IncludedApps` describes application bundles that the PKG actually
installs. It is required for macOS and must contain between 1 and 500 entries.
Every entry requires:

| Manifest field | Source metadata | Rule |
|---|---|---|
| `BundleId` | `CFBundleIdentifier` | Required; duplicate detection uses ordinal, case-sensitive equality |
| `BundleVersion` | `CFBundleShortVersionString` | Required for every `pkg` and `lob` entry |
| `BundleBuildVersion` | `CFBundleVersion` | Required for every `lob` entry; omit for `pkg` |

The list is declarative. Never invent a bundle identifier or version, and do not
assume that the root `PackageVersion` is either bundle version field. If metadata is
unknown, ask for it or report that authoring is blocked.

Bundle IDs that differ only by case are distinct under this contract, although an
actual macOS bundle normally follows a stable lower-case convention. Keep the exact
spelling supplied by the authoritative metadata.

## Primary bundle selection

`Detection.PrimaryBundleId` is optional. When omitted, `IncludedApps[0]` is the
primary entry. Do not materialize a default selector, because omission preserves the
existing manifest meaning and hash behavior.

When specified, matching is ordinal and case-sensitive. A declared entry matches if:

```text
entry.BundleId == PrimaryBundleId
or
entry.BundleId starts with PrimaryBundleId + "."
```

The selector must be non-empty, non-whitespace, and resolve to exactly one entry.
Zero matches and two or more matches are validation failures. The dot is part of the
prefix rule: a selector such as `com.example.app` must not match
`com.example.application`.

Examples of selector outcomes:

| Selector | Declared IDs | Result |
|---|---|---|
| `com.example.client` | `com.example.client`, `com.example.helper` | exact one-match; valid |
| `com.example.client` | `com.example.client.main`, `com.example.helper` | segment-prefix one-match; valid |
| `com.example.client` | `com.example.client.main`, `com.example.client.agent` | two matches; reject as ambiguous |
| `com.example.app` | `com.example.application` | no match; reject |

Selecting a non-first entry changes only the Graph primary projection. Preserve the
manifest's list order and do not move the selected entry to the top in YAML.

## PKG and LOB projection

The target Relaypublisher mapping uses the selected entry as follows:

| App type | Graph collection | Selected primary fields | Build field |
|---|---|---|---|
| `pkg` | `includedApps` | `primaryBundleId` and `primaryBundleVersion` | `BundleBuildVersion` is omitted and not mapped |
| `lob` | `childApps` | top-level `bundleId`; selected version values also populate the top-level primary fields | `BundleVersion` maps to `buildNumber`; `BundleBuildVersion` maps to `versionNumber` |

The payload projection may put the selected entry first for Graph. That is not a
reason to reorder or normalize the source manifest.

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

## Static validation checklist

Review these invariants before invoking the CLI. The bundled checker
(`scripts/manifest_policy.py`) enforces items 1–6 automatically and reports each
violation under the listed `RP0xx` code; items 7–8 are authoring discipline the
checker cannot fully verify on its own.

1. `Platform` is `macos` and `InstallerType` is `pkg` (`RP001`), with no Windows-only
   `Package`/`Install` fields on the entry and exactly one `Source` object (`RP003`).
2. `AppType` is `pkg` or `lob` (or is omitted only where the target schema explicitly
   defines the default as `pkg`) (`RP002`).
3. The entry has one PKG `Source`, required `Requirements`, and `Detection` fields
   required by the target schema (`RP003`).
4. `IncludedApps` has 1–500 entries (`RP004`), no ordinal/case-sensitive duplicate
   `BundleId` (`RP006`), non-empty `BundleId`/`BundleVersion` values (`RP005`), and no
   fields outside `BundleId`/`BundleVersion`/`BundleBuildVersion` (`RP012`).
5. Each LOB entry has a non-empty `BundleBuildVersion` (`RP007`); no PKG entry
   generates one (`RP008`). `AppType: lob` also requires a non-empty root `Icon`
   (`RP011`).
6. A present `PrimaryBundleId` is non-blank (`RP009`) and has exactly one exact or
   dot-segment-prefix match (`RP010`).
7. Updaters are omitted deliberately rather than represented by a new exclusion
   property.
8. The YAML order and unrelated fields remain unchanged.

Use the Relaypublisher CLI without packaging or publication:

```bash
relaypublisher validate --repo-root "$RELAYPUBLISHER_REPO" --manifest "$MANIFEST"
```

```powershell
relaypublisher validate --repo-root $RelaypublisherRepo --manifest $Manifest
```

`validate` is not a package-inspection command and should not download the source.
It may still check local assets referenced by the manifest. Do not add `--force`.

If a CLI is not installed, or an older CLI does not understand
`PrimaryBundleId`/`BundleBuildVersion`, report validation as unavailable or a
version mismatch. Keep the new fields intact; do not make a lossy compatibility edit.

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
      PrimaryBundleId: com.example.contoso.client
      IncludedApps:
        - BundleId: com.example.contoso.client
          BundleVersion: "4.2.0"
        - BundleId: com.example.contoso.helper
          BundleVersion: "4.2.0"
```

`com.example.contoso.client` is an exact, unambiguous match. An updater that is
present in the PKG but should not gate detection is intentionally absent from this
list.

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
      PrimaryBundleId: com.example.contoso.lob.main
      IncludedApps:
        - BundleId: com.example.contoso.lob.main
          BundleVersion: "4.2.0"
          BundleBuildVersion: "4200"
        - BundleId: com.example.contoso.lob.helper
          BundleVersion: "4.2.0"
          BundleBuildVersion: "4200"
```

For the LOB example, both `BundleBuildVersion` values are required and must be
replaced with the respective bundles' actual `CFBundleVersion` values. The icon path
must point to an existing supported image in the target repository. The PKG example
does not contain `BundleBuildVersion` because that field is not part of the PKG
mapping.

## Fixtures

`../tests/fixtures/` contains one manifest per checklist scenario above, used by
`../tests/test_manifest_policy.py`:

| Fixture | Checklist item(s) exercised |
|---|---|
| `valid-pkg-multibundle.yaml` | Full valid shape; the updater is intentionally omitted from `IncludedApps` (item 7) |
| `valid-lob-multibundle.yaml` | Full valid LOB shape, including `BundleBuildVersion` and root `Icon` (items 5, 6) |
| `valid-primary-prefix-match.yaml` | Dot-segment-prefix primary match (item 6) |
| `invalid-dmg.yaml` | Rejects `InstallerType: dmg` (`RP001`, item 1) |
| `invalid-ambiguous-primary.yaml` | Rejects a selector matching two entries (`RP010`, item 6) |
| `invalid-unresolved-primary.yaml` | Rejects a selector with zero matches; confirms the dot is part of the prefix rule (`RP010`, item 6) |
| `invalid-duplicate-bundleid.yaml` | Rejects an ordinal, case-sensitive duplicate `BundleId` (`RP006`, item 4) |
| `invalid-lob-missing-build.yaml` | Rejects a `lob` entry missing `BundleBuildVersion` (`RP007`, item 5) |
| `invalid-pkg-with-build.yaml` | Rejects a `pkg` entry that fabricates `BundleBuildVersion` (`RP008`, item 5) |
