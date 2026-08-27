# Relaypublisher Manifest Implementation Plan

## Scope

- Parent issue: #35
- Plugin version: 0.1.0
- Marketplace category: Developer Tools
- Child issues: #36 plugin structure and marketplace metadata, #38 macOS PKG/LOB authoring and validation guidance, #37 structural validation and independent forward testing

## macOS PKG/LOB contract

The macOS source is always a PKG. `AppType: pkg` maps the selected primary bundle to the Graph `includedApps` collection's `primaryBundleId`/`primaryBundleVersion`; `AppType: lob` maps it to the `childApps` top-level `bundleId`, with `BundleVersion`/`BundleBuildVersion` populating `buildNumber`/`versionNumber`. `InstallerType: dmg` and any DMG source are unsupported and must be rejected rather than translated into a PKG shape.

`Detection.IncludedApps` declares 1–500 real installed bundles. `BundleId` duplicate detection is ordinal and case-sensitive. `BundleVersion` (`CFBundleShortVersionString`) is required for every entry; `BundleBuildVersion` (`CFBundleVersion`) is required for every `lob` entry and must be omitted for `pkg` entries. A bundled updater that should not gate detection is excluded by omission from `IncludedApps`; there is no separate exclusion field.

`Detection.PrimaryBundleId` is optional. When present, matching is ordinal and case-sensitive: an entry matches if its `BundleId` equals the selector or starts with `selector + "."`. Exactly one entry must match — zero or multiple matches are rejected. When omitted, `IncludedApps[0]` remains primary. Selecting a non-first entry never reorders the manifest; reordering is a Graph-payload concern only.

## Boundaries

This skill authors, updates, and statically validates manifests only. It never runs `package` or `publish`, never downloads/unpacks/inspects PKG contents, never passes `--force`, never calls Microsoft Graph, and never makes tenant/app/assignment changes. It also never invents bundle metadata: missing `BundleId`/`BundleVersion`/`BundleBuildVersion` values block authoring with a request for the exact values instead of a fabricated placeholder.

## Validation

Two independent layers exist, and passing the first is not a substitute for the second:

1. **Bundled checker** (`scripts/manifest_policy.py`) — a CLI-independent, PyYAML-based static checker for the invariants above (`RP001`–`RP012`). It never touches the network or a package payload and is not the Relaypublisher schema authority; it exists so the contract can be checked even when the target repository's `relaypublisher` CLI is unavailable.
2. **Relaypublisher CLI** (`relaypublisher validate`) — the authoritative validator from the target repository, when available and new enough to understand `Detection.PrimaryBundleId` and `IncludedApps[].BundleBuildVersion`.

Test coverage:

- 28 unit tests in `tests/test_manifest_policy.py` (26 run without any dependency, against dicts directly; 2 exercise the checked-in YAML fixtures and require PyYAML)
- 9 fixture manifests in `tests/fixtures/` covering every forward-test scenario from issue #37: valid multi-bundle PKG (with an intentionally omitted updater), valid multi-bundle LOB, valid dot-segment-prefix primary selection, unsupported DMG, ambiguous primary selector, unresolved primary selector (`com.example.app` must not match `com.example.application`), duplicate `BundleId`, missing LOB `BundleBuildVersion`, and a `pkg` entry incorrectly carrying `BundleBuildVersion`
- Marketplace structure validation via `scripts/validate_marketplaces.py` (frontmatter, links, LICENSE, Claude/Codex manifest parity)

## Implementation notes

- The bundled checker requires PyYAML (`pip install pyyaml`) to parse manifest files; a self-written YAML parser was rejected as a bigger correctness risk than the dependency. The judgment logic (`evaluate()`) is a pure function over an already-parsed `dict`, so it has no PyYAML dependency itself and is fully testable without it.
- `AppType: lob` requires a root `Icon`; the bundled checker only verifies the path exists when `--repo-root` is supplied, since checking a path with no repository context would be a false negative risk, not a real check.
- An omitted `AppType` is treated as `pkg` by both the skill guidance and the bundled checker, matching the target schema's stated default.
- `agents/openai.yaml` sets `policy.allow_implicit_invocation: true`, which is not present on other plugins in this repository. This is intentional: issue #36's acceptance criteria require the skill to "remain implicitly discoverable," and other plugins in this repository predate that requirement.
