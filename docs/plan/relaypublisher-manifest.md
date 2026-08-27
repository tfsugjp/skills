# Relaypublisher Manifest Implementation Plan

## Scope

- Parent issue: #35
- Plugin version: 0.1.0
- Marketplace category: Developer Tools
- Child issues: #36 plugin structure and marketplace metadata, #38 macOS PKG/LOB authoring and validation guidance, #37 structural validation and independent forward testing
- Follow-up parent issue: #42 (Assignments/Categories/macOS Scripts), with sub-issues #43 (Assignments), #44 (Categories), #45 (macOS Scripts)

Issue #35 scoped this plugin to macOS PKG applications only. Windows Win32
authoring/validation support was added afterward, at the user's request, once
it became clear the underlying Relaypublisher tool has supported
`Platform: windows` / `InstallerType: win32` manifests since before its macOS
support existed (see `doc/01-manifest-schema.md` §5.1/§5.2 and
`ManifestValidator.cs` in the Relaypublisher tool repository) — this skill had
simply never been extended to cover it. There is no separate tracking issue
for the Windows addition; it is documented here and in the SKILL/reference
files directly.

## macOS PKG/LOB contract

The macOS source is always a PKG. `AppType: pkg` maps the selected primary bundle to the Graph `includedApps` collection's `primaryBundleId`/`primaryBundleVersion`; `AppType: lob` maps it to the `childApps` top-level `bundleId`, with `BundleVersion`/`BundleBuildVersion` populating `buildNumber`/`versionNumber`. `InstallerType: dmg` and any DMG source are unsupported and must be rejected rather than translated into a PKG shape.

`Detection.IncludedApps` declares 1–500 real installed bundles. `BundleId` duplicate detection is ordinal and case-sensitive. `BundleVersion` (`CFBundleShortVersionString`) is required for every entry; `BundleBuildVersion` (`CFBundleVersion`) is required for every `lob` entry and must be omitted for `pkg` entries. A bundled updater that should not gate detection is excluded by omission from `IncludedApps`; there is no separate exclusion field.

`Detection.PrimaryBundleId` is optional. When present, matching is ordinal and case-sensitive: an entry matches if its `BundleId` equals the selector or starts with `selector + "."`. Exactly one entry must match — zero or multiple matches are rejected. When omitted, `IncludedApps[0]` remains primary. Selecting a non-first entry never reorders the manifest; reordering is a Graph-payload concern only.

## Windows Win32 contract

The Windows source is a `.intunewin` built from `Package.IntuneWin.SetupFile` plus optional `Package.RepositoryFiles` (repo-relative files staged verbatim) and `Package.ExternalFiles` (binaries fetched from a source provider). `ExternalFiles` entries use the same source-item shape as the macOS `Source` field (`Type: publicHttp | githubRelease | azureBlob`, a required 64-hex-char `Sha256`, type-specific required fields, and `Auth` rules: `token` requires `SecretName`, `azureBlob` requires `Auth.Type: workloadIdentity`, `githubRelease` forbids it).

`Install.CommandLine`/`UninstallCommandLine` are required; `InstallExperience` is `system` or `user`; `RestartBehavior` is `suppress`, `allow`, or `force`. `ReturnCodes` is optional (Intune's default set applies when omitted) but every entry's `Type` must be one of `success`/`softReboot`/`hardReboot`/`retry`/`failed`. `Detection.Type` must be `script`, with a required `Detection.ScriptFile`. `AppType` and `Source` are macOS-only and must not appear on a `Platform: windows` entry — use `Package` instead.

`Architecture` (app-level) must be `x64` or `arm64`; when `Requirements.Architecture` is also set, it must match exactly (ordinal). `Requirements.MinimumOSVersion` is required for both platforms.

## Assignments, Categories, and macOS Scripts

`Assignments` and `Categories` are shared verbatim by Windows and macOS entries; macOS pre/post-install `Scripts` applies only to `AppType: pkg`. All three are local, Graph-free validation surfaces — the checker validates only the manifest shape and never contacts Microsoft Graph (no category-name tenant resolution, no assignment application).

`Assignments[]` entries: `Target` (`group` default, `allDevices`, `allLicensedUsers`), `GroupId` (valid GUID, required only for `group`), `Mode` (`include` default, `exclude`), `Intent` (required for `include`; `required`/`available`/`uninstall`), `FilterId`/`FilterMode`, and `Settings.Notifications` (documented by the target tool as "Win32 only" in intent, but not platform-restricted by its actual validator — the checker matches that and validates the enum on any platform without rejecting `Settings` on macOS). No two entries in one app's list may resolve to the same `(effective Target, GroupId, effective Mode)`. A macOS `AppType: pkg` entry forbids `Intent: uninstall`; `AppType: lob` and every Windows entry allow it.

`Categories[]`: every element non-blank, no outer whitespace, no case-insensitive duplicate within one entry. Omitting `Categories` leaves existing app-category relationships untouched; `Categories: []` clears them; one or more entries fully synchronizes the desired set — the checker must not conflate omission with an empty list.

macOS `Scripts` (`AppType: pkg` only): forbidden on `Platform: windows` and `AppType: lob`; at least one of `PreInstall`/`PostInstall` required when present; each path must be a safe repository-relative `.sh` path. With `--repo-root`, the checker additionally confirms the file exists, has no UTF-8 BOM, starts with a shebang, and stays under the 15,360-character limit after CRLF/CR-to-LF normalization — mirroring the existing `Icon` `--repo-root` pattern and the target tool's own `ManifestAssetValidator`.

## Boundaries

This skill authors, updates, and statically validates manifests only. It never runs `package` or `publish`, never downloads/unpacks/inspects PKG or `.intunewin` contents, never passes `--force`, never calls Microsoft Graph, and never makes tenant/app/assignment changes (authoring the `Assignments`/`Categories` manifest fields is in scope; applying them via Graph is not). It also never invents bundle metadata: missing `BundleId`/`BundleVersion`/`BundleBuildVersion`/`Sha256`/etc. values block authoring with a request for the exact values instead of a fabricated placeholder.

## Validation

Two independent layers exist, and passing the first is not a substitute for the second:

1. **Bundled checker** (`scripts/manifest_policy.py`) — a CLI-independent, PyYAML-based static checker for the invariants above (`RP001`–`RP079`, see the per-platform reference docs for the full code table). It never touches the network or a package payload and is not the Relaypublisher schema authority; it exists so the contract can be checked even when the target repository's `relaypublisher` CLI is unavailable. Its enum values and field requirements were transcribed directly from the Relaypublisher tool's own `ManifestValidator.cs`/`ManifestValues.cs`/`ManifestAssetValidator.cs`/`PathSafety.cs` (not guessed), to keep it accurate.
2. **Relaypublisher CLI** (`relaypublisher validate`) — the authoritative validator from the target repository, when available and new enough to understand `Detection.PrimaryBundleId` and `IncludedApps[].BundleBuildVersion`.

Test coverage:

- 108 unit tests in `tests/test_manifest_policy.py` (most run without any dependency, against dicts directly; the fixture-file tests exercise the checked-in YAML fixtures and require PyYAML)
- 20 fixture manifests in `tests/fixtures/`: 9 macOS (covering every forward-test scenario from issue #37 — valid multi-bundle PKG with an intentionally omitted updater, valid multi-bundle LOB, valid dot-segment-prefix primary selection, unsupported DMG, ambiguous/unresolved primary selector, duplicate `BundleId`, missing LOB `BundleBuildVersion`, a `pkg` entry incorrectly carrying `BundleBuildVersion`), 5 Windows/cross-platform (valid Win32 x64/arm64, `AppType` wrongly set on a Windows entry, missing `Package`, unsupported `RestartBehavior`), 1 unsupported-`Platform` case, and 4 Assignments/Categories/Scripts (valid combination, duplicate assignment target, duplicate category name, `Scripts` set on a Windows entry) — plus 3 standalone script files (`scripts/valid-preinstall.sh`, `scripts/no-shebang.sh`, `scripts/with-bom.sh`) used by the `--repo-root`-gated Scripts tests
- Marketplace structure validation via `scripts/validate_marketplaces.py` (frontmatter, links, LICENSE, Claude/Codex manifest parity)

## Implementation notes

- The bundled checker requires PyYAML (`pip install pyyaml`) to parse manifest files; a self-written YAML parser was rejected as a bigger correctness risk than the dependency. The judgment logic (`evaluate()`) is a pure function over an already-parsed `dict`, so it has no PyYAML dependency itself and is fully testable without it.
- `AppType: lob` requires a root `Icon`; the bundled checker only verifies the path exists when `--repo-root` is supplied, since checking a path with no repository context would be a false negative risk, not a real check.
- An omitted `AppType` is treated as `pkg` by both the skill guidance and the bundled checker, matching the target schema's stated default.
- An app entry with a `Platform` other than `windows` or `macos` is rejected (`RP013`) rather than silently skipped. Before Windows support existed, the checker deliberately skipped any non-macOS `Platform` value (documented as "out of scope, left unchanged"); that skip behavior is now gone, since the checker validates both platforms Relaypublisher itself recognizes.
- The macOS `Source` field and Windows `Package.ExternalFiles[]` entries share one source-item validator (`RP020`-`RP027`), matching the target tool's own shared `SourceManifest` model — this also retroactively made the macOS `Source` check stricter than PR #39's original version (which only checked that `Source` was present, not its internal shape).
- `Assignments`/`Categories`/macOS `Scripts` (issues #43/#44/#45) were the follow-up items explicitly deferred when Windows support was added; they are no longer out of scope. `GroupId`/`FilterId` GUID validation uses Python's standard `uuid.UUID` parser (matching `Guid.TryParse` semantics closely enough for manifest authoring). Path-safety for `Scripts.PreInstall`/`PostInstall` mirrors the target tool's `PathSafety.IsSafeRelativePath` (reject absolute paths under both POSIX and Windows conventions, and any `..` segment) rather than reimplementing it from scratch.
- `agents/openai.yaml` sets `policy.allow_implicit_invocation: true`, which is not present on other plugins in this repository. This is intentional: issue #36's acceptance criteria require the skill to "remain implicitly discoverable," and other plugins in this repository predate that requirement.
