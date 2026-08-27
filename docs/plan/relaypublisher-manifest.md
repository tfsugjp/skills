# Relaypublisher Manifest Implementation Plan

## Scope

- Parent issue: #35
- Plugin version: 0.1.0
- Marketplace category: Developer Tools
- Child issues: #36 plugin structure and marketplace metadata, #38 macOS PKG/LOB authoring and validation guidance, #37 structural validation and independent forward testing

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

## Boundaries

This skill authors, updates, and statically validates manifests only. It never runs `package` or `publish`, never downloads/unpacks/inspects PKG or `.intunewin` contents, never passes `--force`, never calls Microsoft Graph, and never makes tenant/app/assignment changes. It also never invents bundle metadata: missing `BundleId`/`BundleVersion`/`BundleBuildVersion`/`Sha256`/etc. values block authoring with a request for the exact values instead of a fabricated placeholder.

**Out of scope for both platforms** (deliberately not implemented, despite being locally/statically checkable): `Assignments` (target/intent/filter validation, doc/01-manifest-schema.md §5.5), `Categories` (§5.8), and macOS pre/post-install `Scripts` (§5.4.2). These are real, Graph-free validation surfaces in the target Relaypublisher tool, but they were judged to be a separate follow-up rather than part of "add Windows support" — flag to the user if broader schema coverage is wanted.

## Validation

Two independent layers exist, and passing the first is not a substitute for the second:

1. **Bundled checker** (`scripts/manifest_policy.py`) — a CLI-independent, PyYAML-based static checker for the invariants above (`RP001`–`RP044`, see the per-platform reference docs for the full code table). It never touches the network or a package payload and is not the Relaypublisher schema authority; it exists so the contract can be checked even when the target repository's `relaypublisher` CLI is unavailable. Its enum values and field requirements were transcribed directly from the Relaypublisher tool's own `ManifestValidator.cs`/`ManifestValues.cs` (not guessed), to keep it accurate.
2. **Relaypublisher CLI** (`relaypublisher validate`) — the authoritative validator from the target repository, when available and new enough to understand `Detection.PrimaryBundleId` and `IncludedApps[].BundleBuildVersion`.

Test coverage:

- 65 unit tests in `tests/test_manifest_policy.py` (most run without any dependency, against dicts directly; the fixture-file tests exercise the checked-in YAML fixtures and require PyYAML)
- 16 fixture manifests in `tests/fixtures/`: 9 macOS (covering every forward-test scenario from issue #37 — valid multi-bundle PKG with an intentionally omitted updater, valid multi-bundle LOB, valid dot-segment-prefix primary selection, unsupported DMG, ambiguous/unresolved primary selector, duplicate `BundleId`, missing LOB `BundleBuildVersion`, a `pkg` entry incorrectly carrying `BundleBuildVersion`) plus 5 Windows/cross-platform (valid Win32 x64 with `publicHttp`, valid Win32 arm64 with `githubRelease`+token auth, `AppType` wrongly set on a Windows entry, missing `Package`, unsupported `RestartBehavior`) and 1 unsupported-`Platform` case
- Marketplace structure validation via `scripts/validate_marketplaces.py` (frontmatter, links, LICENSE, Claude/Codex manifest parity)

## Implementation notes

- The bundled checker requires PyYAML (`pip install pyyaml`) to parse manifest files; a self-written YAML parser was rejected as a bigger correctness risk than the dependency. The judgment logic (`evaluate()`) is a pure function over an already-parsed `dict`, so it has no PyYAML dependency itself and is fully testable without it.
- `AppType: lob` requires a root `Icon`; the bundled checker only verifies the path exists when `--repo-root` is supplied, since checking a path with no repository context would be a false negative risk, not a real check.
- An omitted `AppType` is treated as `pkg` by both the skill guidance and the bundled checker, matching the target schema's stated default.
- An app entry with a `Platform` other than `windows` or `macos` is rejected (`RP013`) rather than silently skipped. Before Windows support existed, the checker deliberately skipped any non-macOS `Platform` value (documented as "out of scope, left unchanged"); that skip behavior is now gone, since the checker validates both platforms Relaypublisher itself recognizes.
- The macOS `Source` field and Windows `Package.ExternalFiles[]` entries share one source-item validator (`RP020`-`RP027`), matching the target tool's own shared `SourceManifest` model — this also retroactively made the macOS `Source` check stricter than PR #39's original version (which only checked that `Source` was present, not its internal shape).
- `agents/openai.yaml` sets `policy.allow_implicit_invocation: true`, which is not present on other plugins in this repository. This is intentional: issue #36's acceptance criteria require the skill to "remain implicitly discoverable," and other plugins in this repository predate that requirement.
