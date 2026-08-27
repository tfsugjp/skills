---
name: relaypublisher-manifest
description: 'Create, update, and statically validate Relaypublisher YAML manifests, including macOS PKG and LOB manifests that declare multiple application bundles. Use when bundle detection, primary bundle selection, or macOS manifest fields need authoring or review. Do not use for packaging, publishing, force acknowledgements, Graph calls, or tenant changes.'
compatibility: 'Bundled checker (scripts/manifest_policy.py) requires Python 3.10+ and PyYAML (pip install pyyaml). Full validation additionally requires a Relaypublisher CLI or source revision that supports Detection.PrimaryBundleId and IncludedApps[].BundleBuildVersion.'
---

# Relaypublisher Manifest

Use this skill for manifest-only work in a Relaypublisher repository. The goal is a
small, reviewable YAML change that describes the intended application metadata and
passes the target repository's schema validation. It does not acquire or inspect a
package and it does not change Intune state.

## Establish the target contract

Before editing a manifest:

1. Read the target repository's canonical manifest schema and relevant examples.
   Prefer its current documentation and source model/validator over remembered
   Relaypublisher behavior. In the standard repository these are the manifest schema
   document and the manifest model, validation, bundle-selector, and macOS payload
   mapping code.
2. Confirm the CLI version or source revision supports `Detection.PrimaryBundleId`
   and `IncludedApps[].BundleBuildVersion`. Run `relaypublisher --version` (or the
   target repository's equivalent) and check it against the repository's changelog
   for the revision that introduced those fields. A CLI that ignores those fields is
   not a compatible validator for this work.
3. Obtain every bundle identifier and version from user-supplied or otherwise
   authoritative package metadata. Never guess a bundle identifier, a
   `CFBundleShortVersionString`, or a `CFBundleVersion`, and never silently replace
   an unknown value with `PackageVersion`.

Read [macOS manifest contract](references/macos-manifest.md) for the detailed rules,
field mapping, examples, and static-validation checklist.

## Scope and hard boundaries

- Author, update, and statically validate Relaypublisher manifests only.
- This skill's macOS PKG/LOB contract and bundled checker govern macOS entries only.
  Leave non-macOS entries in a manifest unchanged and unchecked.
- For macOS, the source is a PKG: use `InstallerType: pkg` and `AppType: pkg` or
  `AppType: lob`. DMG installers are unsupported; do not translate a DMG into a PKG
  manifest or add a guessed DMG schema.
- A multi-bundle manifest has one macOS PKG source and an explicit
  `Detection.IncludedApps` list. It is not a manifest containing multiple independent
  package sources.
- Do not run `package` or `publish`, download/unpack/inspect installer contents, pass
  `--force`, call Microsoft Graph, or make tenant/app/assignment changes.
- Do not add an updater exclusion list or an automatic updater allow/deny heuristic.
  Omit an updater from `IncludedApps` when it must not participate in detection.

## Author or update a manifest

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

If required bundle metadata is unavailable, stop with a clear request for the exact
values and leave the manifest unchanged. A syntactically valid but fabricated
`IncludedApps` entry is not a successful result.

## Static validation

Validation has two independent layers. Passing the first is not a substitute for the
second — report both separately and never claim Relaypublisher validation passed
because the bundled checker passed.

### 1. Bundled checker (always available)

Run the CLI-independent checker bundled with this skill against every changed
macOS entry. It requires PyYAML (`pip install pyyaml`) and never downloads the
`Source`, inspects the PKG, or touches the network:

```bash
python scripts/manifest_policy.py --manifest "$MANIFEST" --repo-root "$REPO_ROOT"
```

PowerShell 7 equivalent:

```powershell
python scripts\manifest_policy.py --manifest $Manifest --repo-root $RepoRoot
```

`--repo-root` is optional and only used to confirm an `AppType: lob` `Icon` path
exists; omit it when no repository context is available. Exit code `0` means no
contract violation was found; `1` means at least one was; `3` means PyYAML is not
installed. Pass `--json` for machine-readable findings. This checker is not the
Relaypublisher schema authority — it only catches the manifest-authoring mistakes
this skill is responsible for (unsupported DMG, malformed `IncludedApps`,
ambiguous/unresolved primary selectors, and PKG/LOB field misuse).

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
icon, but it must not download the `Source` or inspect the PKG. Check the output for
schema errors, macOS app-type restrictions, `IncludedApps` count/duplicate errors,
primary-selector errors, and missing LOB build values. Do not claim Relaypublisher
validation passed if the command is unavailable.

When the CLI is unavailable, rely on the bundled checker plus a syntax and contract
review using the target repository's schema tooling if present, then report that
Relaypublisher validation is incomplete. When the CLI is too old or rejects the new
fields, report a version mismatch and retain `PrimaryBundleId` and
`BundleBuildVersion`; never delete or downgrade those fields to make an old command
pass.

Finish by reporting the changed manifest path(s), the bundle metadata source, the
bundled-checker result, the Relaypublisher CLI command/result (or its unavailability),
and any validation limitation. Keep package, publish, Graph, and tenant work for a
separately authorized task.
