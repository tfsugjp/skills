# Windows Win32 Manifest Contract

Use this reference when authoring or reviewing a Windows entry in a
Relaypublisher manifest. The target repository's schema and validator remain
authoritative if a future schema revision changes a field outside this
contract. Field names, enum values, and required-ness below are transcribed
directly from the target repository's `ManifestValidator.cs` and
`ManifestValues.cs` (Win32 has been supported there since before macOS was
added), not guessed from the sample manifest alone.

## Supported shape

The supported Windows installer is Win32 (`.intunewin`, built by the target
tool's `IntuneWinAppUtil` integration — this skill never builds or inspects
one). The app entry must use:

```yaml
Platform: windows
Architecture: x64        # or arm64
InstallerType: win32
```

`AppType` and `Source` are macOS-only fields and must not appear on a Windows
entry: use `Package` for the installer composition instead of `Source`. There
is no other installer type for Windows in this contract.

## Package

```yaml
Package:
  IntuneWin:
    SetupFile: install.ps1               # required, non-empty; staging-relative

  RepositoryFiles:                        # optional; files copied from the repo as-is
    - Source: scripts/windows/x64/install.ps1     # required, repo-relative
      Destination: install.ps1                    # required, staging-relative

  ExternalFiles:                          # optional; binaries fetched from a source provider
    - Type: publicHttp | githubRelease | azureBlob
      Destination: bin/contoso-tool.exe   # required, staging-relative
      Sha256: "<64 hex chars>"            # required for every entry
      Auth: {...}                        # see "Source-item shape" below
```

`IntuneWin.SetupFile` is required and non-empty. `RepositoryFiles` and
`ExternalFiles` may each be empty or omitted, but every entry present must
satisfy the rules above/below.

## Source-item shape (shared with macOS `Source`)

Windows `ExternalFiles` entries and the macOS `Source` field use the identical
shape, so the same static checks apply to both:

| Field | Required when | Rule |
|---|---|---|
| `Type` | always | one of `publicHttp`, `githubRelease`, `azureBlob` |
| `Destination` | always | non-empty |
| `Sha256` | always | 64-character hexadecimal string |
| `Url` | `Type: publicHttp` | non-empty |
| `Owner`, `Repository`, `Tag`, `AssetName` | `Type: githubRelease` | each non-empty |
| `AccountName`, `Container`, `BlobName` | `Type: azureBlob` | each non-empty |
| `Auth.Type` | if `Auth` is present | one of `none`, `token`, `workloadIdentity` |
| `Auth.SecretName` | `Auth.Type: token` | non-empty (names the CI secret/env var) |

Two additional cross-field rules:

- `Type: azureBlob` requires `Auth.Type: workloadIdentity`. Use `publicHttp`
  for anonymously readable URLs instead of forcing blob auth.
- `Type: githubRelease` forbids `Auth.Type: workloadIdentity` (use `token` or
  `none`/omit `Auth`).

## Install

```yaml
Install:
  CommandLine: powershell.exe -ExecutionPolicy Bypass -File .\install.ps1
  UninstallCommandLine: powershell.exe -ExecutionPolicy Bypass -File .\uninstall.ps1
  InstallExperience: system            # system | user
  RestartBehavior: suppress            # suppress | allow | force
  ReturnCodes:                         # optional; Intune's default set applies when omitted
    - Code: 0
      Type: success                    # success | softReboot | hardReboot | retry | failed
    - Code: 3010
      Type: softReboot
```

`CommandLine`, `UninstallCommandLine`, `InstallExperience`, and
`RestartBehavior` are all required and non-empty. When `ReturnCodes` is
omitted, Intune applies its documented default set (`0`/`1707` success,
`3010` softReboot, `1641` hardReboot, `1618` retry) — do not fabricate that
list in the manifest merely to make it explicit.

## Detection

```yaml
Detection:
  Type: script                  # the only supported Detection.Type
  ScriptFile: scripts/windows/common/detect.ps1   # required when Type is script
  RunAs32Bit: false              # optional
  EnforceSignatureCheck: false   # optional
```

`Detection.Type` is required and must be `script`; `ScriptFile` is then
required and non-empty. Windows has no other detection mechanism in this
contract — do not invent a bundle-based detection scheme.

## Requirements and Architecture

```yaml
Requirements:
  MinimumOSVersion: "10.0.19045"   # build number; required for every platform
  Architecture: x64                # must match the app-level Architecture exactly
```

The app-level `Architecture` must be `x64` or `arm64`. `Requirements.Architecture`
is optional, but when present it must equal the app-level `Architecture`
exactly (ordinal comparison) — a mismatch is rejected, not silently corrected.
`Requirements.MinimumOSVersion` is required for both Windows and macOS
entries.

## Assignments (shared with macOS)

```yaml
Assignments:
  - Target: group             # group (default) | allDevices | allLicensedUsers
    GroupId: "<guid>"         # required (valid GUID) when Target is group; forbidden otherwise
    Mode: include              # include (default) | exclude
    Intent: required           # required when Mode is include; required | available | uninstall
    FilterId: "<guid>"        # optional; assignment filter GUID
    FilterMode: include        # required when FilterId is set; include | exclude
    Settings:                  # optional; Win32 only
      Notifications: showAll   # showAll | showReboot | hideAll
      RestartGracePeriodMinutes: 1440
```

`Assignments` is shared verbatim by Windows and macOS entries. No two entries
in one app's `Assignments` list may resolve to the same
`(effective Target, GroupId, effective Mode)` tuple — an `include` and an
`exclude` assignment for the same group are different Graph targets and are
not duplicates. A macOS `AppType: pkg` entry (the default) forbids
`Intent: uninstall`; macOS `AppType: lob` and every Windows entry allow it.

## Categories (shared with macOS)

```yaml
Apps:
  - Platform: windows
    Categories:
      - Business Apps
      - Productivity
```

Every element must be non-blank, have no leading/trailing whitespace, and be
unique within the entry's list under a case-insensitive comparison — no count
or length limit is imposed locally. `Categories` is nullable: omitting it
leaves existing app-category relationships untouched (no Graph call at all);
`Categories: []` clears all of them; one or more entries fully synchronizes
the desired set. Category names are matched against the tenant catalog only
at publish/dry-run time — this checker never resolves them against Graph, so
a name that does not exist in the tenant is not caught here.

## Static validation checklist

Review these invariants before invoking the CLI. The bundled checker
(`scripts/manifest_policy.py`) enforces every item below automatically and
reports each violation under the listed `RP0xx` code.

1. `Platform` is `windows` and `InstallerType` is `win32` (`RP013`, `RP029`).
2. `Architecture` is `x64` or `arm64`, and `Requirements.Architecture` (if set)
   matches it exactly (`RP014`, `RP016`).
3. `Requirements.MinimumOSVersion` is non-empty (`RP015`).
4. `AppType` and `Source` are not set on this entry (`RP030`, `RP031`).
5. `Package.IntuneWin.SetupFile` is non-empty (`RP032`, `RP033`); every
   `Package.RepositoryFiles` entry has non-empty `Source`/`Destination`
   (`RP034`); every `Package.ExternalFiles` entry satisfies the source-item
   shape above (`RP020`-`RP027`).
6. `Install.CommandLine`/`UninstallCommandLine` are non-empty, `InstallExperience`
   is `system` or `user`, `RestartBehavior` is `suppress`/`allow`/`force`, and
   every present `ReturnCodes[].Type` is a supported value (`RP035`-`RP039`).
7. `Detection.Type` is `script` and `Detection.ScriptFile` is non-empty
   (`RP040`, `RP041`).
8. `Assignments` entries use supported `Target`/`Mode`/`Intent`/`FilterMode`/
   `Settings.Notifications` values, `GroupId`/`FilterId` are valid GUIDs when
   present, and no two entries duplicate the same target (`RP050`-`RP057`).
9. `Categories` entries are non-blank, have no outer whitespace, and contain
   no case-insensitive duplicates (`RP060`-`RP062`).
10. The YAML order and unrelated fields remain unchanged.

The `.intunewin` build itself is out of scope for this skill — this contract
only governs the manifest, never the packaging step.

## Fixtures

`../tests/fixtures/` contains one manifest per checklist scenario above, used
by `../tests/test_manifest_policy.py`:

| Fixture | Checklist item(s) exercised |
|---|---|
| `valid-windows-win32-x64.yaml` | Full valid shape with a `publicHttp` external file and explicit `ReturnCodes` |
| `valid-windows-win32-arm64.yaml` | Full valid shape with a `githubRelease` external file and `token` auth |
| `invalid-windows-apptype-set.yaml` | Rejects `AppType` set on a Windows entry (`RP030`, item 4) |
| `invalid-windows-missing-package.yaml` | Rejects a Windows entry with no `Package` block (`RP032`, item 5) |
| `invalid-windows-bad-restart-behavior.yaml` | Rejects an unsupported `RestartBehavior` value (`RP038`, item 6) |
| `invalid-unsupported-platform.yaml` | Rejects a `Platform` that is neither `windows` nor `macos` (`RP013`, item 1) |
| `valid-assignments-categories-scripts.yaml` | Valid `Assignments`/`Categories` (macOS entry; the Windows shape is identical) (items 8-9) |
| `invalid-assignment-duplicate-target.yaml` | Rejects two assignments resolving to the same target (`RP057`, item 8) |
| `invalid-categories-duplicate.yaml` | Rejects a case-insensitive duplicate category name (`RP062`, item 9) |
| `invalid-scripts-on-windows.yaml` | Rejects macOS-only `Scripts` set on a Windows entry (`RP070`; see [macos-manifest.md](macos-manifest.md#static-validation-checklist)) |

## Complete examples

The following are concise schema-valid shapes, mirroring the target
repository's own `doc/01-manifest-schema.md` §5.1/§5.2 samples. Replace the
illustrative URL, Azure Blob names, checksums, and repository-relative script
paths with real values before running repository validation.

### Win32 x64 (publicHttp external file)

```yaml
SchemaVersion: "1.0"
PackageIdentifier: Contoso.Tool
PackageName: Contoso Tool
Publisher: Contoso Ltd.
Description: Internal tool for Contoso employees.
PackageVersion: "1.2.3"

Apps:
  - Platform: windows
    Architecture: x64
    InstallerType: win32
    DisplayName: Contoso Tool [Windows x64]

    Package:
      IntuneWin:
        SetupFile: install.ps1
      RepositoryFiles:
        - Source: scripts/windows/x64/install.ps1
          Destination: install.ps1
        - Source: scripts/windows/common/uninstall.ps1
          Destination: uninstall.ps1
        - Source: scripts/windows/common/detect.ps1
          Destination: detect.ps1
      ExternalFiles:
        - Type: publicHttp
          Url: https://example.com/downloads/contoso-tool-1.2.3-x64.exe
          Destination: bin/contoso-tool.exe
          Sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    Install:
      CommandLine: powershell.exe -ExecutionPolicy Bypass -File .\install.ps1
      UninstallCommandLine: powershell.exe -ExecutionPolicy Bypass -File .\uninstall.ps1
      InstallExperience: system
      RestartBehavior: suppress
      ReturnCodes:
        - Code: 0
          Type: success
        - Code: 3010
          Type: softReboot

    Detection:
      Type: script
      ScriptFile: scripts/windows/common/detect.ps1
      RunAs32Bit: false
      EnforceSignatureCheck: false

    Requirements:
      MinimumOSVersion: "10.0.19045"
      Architecture: x64
```

### Win32 arm64 (githubRelease external file with token auth)

```yaml
  - Platform: windows
    Architecture: arm64
    InstallerType: win32
    DisplayName: Contoso Tool [Windows Arm64]

    Package:
      IntuneWin:
        SetupFile: install.ps1
      RepositoryFiles:
        - Source: scripts/windows/arm64/install.ps1
          Destination: install.ps1
        - Source: scripts/windows/common/uninstall.ps1
          Destination: uninstall.ps1
        - Source: scripts/windows/common/detect.ps1
          Destination: detect.ps1
      ExternalFiles:
        - Type: githubRelease
          Owner: contoso
          Repository: internal-tools
          Tag: v1.2.3
          AssetName: contoso-tool-1.2.3-arm64.exe
          Destination: bin/contoso-tool.exe
          Sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
          Auth:
            Type: token
            SecretName: GH_RELEASE_PAT

    Install:
      CommandLine: powershell.exe -ExecutionPolicy Bypass -File .\install.ps1
      UninstallCommandLine: powershell.exe -ExecutionPolicy Bypass -File .\uninstall.ps1
      InstallExperience: system
      RestartBehavior: suppress

    Detection:
      Type: script
      ScriptFile: scripts/windows/common/detect.ps1
      RunAs32Bit: false
      EnforceSignatureCheck: false

    Requirements:
      MinimumOSVersion: "10.0.22621"
      Architecture: arm64
```

The arm64 example omits `ReturnCodes`, so Intune's default return-code set
applies at publish time; that is a valid, deliberate omission, not a gap to
fill in.
