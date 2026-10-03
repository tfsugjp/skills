# Ecosystem release and update rules

Use this reference after the pull request ecosystem and package manager are known. Prefer existing repository authentication and wrappers. Never print credentials, authenticated request headers, or registry configuration values.

## Common release policy

- Query all available versions, not only the Dependabot target or current major.
- Require a timezone-aware publication instant for every active stable candidate.
- Normalize publication instants to UTC and require `published_at <= now - 24 hours`.
- Exclude prerelease, yanked, retracted, unlisted, deprecated, and draft records.
- Treat unparseable versions and mutable tags as blocking evidence.
- For a private registry, continue only when existing authentication returns both version and publication-time metadata.
- Requery immediately before auto-merge. Repeat refresh at most three times when the eligible target changes.

## npm, Yarn, and pnpm

Read the npm packument `versions`, `time`, and per-version `deprecated` fields. Detect the manager from the committed lockfile and package-manager metadata.

Use the matching targeted lock update with lifecycle scripts disabled. The deterministic planner emits argv for npm, Yarn, or pnpm. Compare the manifest before and after, preserve its operator and declaration form, and accept only the expected manifest and lockfile changes.

Official evidence name: npm registry package metadata response documentation.

## NuGet

Discover the V3 service index, then read registration pages and leaves. Require `catalogEntry.version`, `published`, and `listed`. Treat deprecation metadata as ineligible.

Update the project declaration or central package version while retaining its XML form, then run `dotnet restore`. Review `packages.lock.json`, project assets, and central package management files only when they are already part of repository policy.

Official evidence name: NuGet registration base URL resource documentation.

## pip, Poetry, and uv

Use the Python Simple JSON API. Group files by version, reject the version when any required artifact lacks `upload-time`, and use the newest artifact upload time for the 24-hour threshold. Exclude a version only when all published files are yanked; flag mixed yanked state for manual review.

Use the repository's existing lock tool and update only the selected package. The planner supports pip-tools, Poetry, and uv. Never replace the project's lock tool.

Official evidence name: Python Simple Repository API specification.

## Maven and Gradle

Use Maven repository metadata plus a repository search response that provides the version timestamp. A version without a verifiable timestamp is blocked.

Preserve properties, dependency-management entries, and version catalogs. Use the committed Maven or Gradle wrapper. Regenerate existing dependency locks or verification metadata and reject unrelated build-file changes. Do not execute untrusted init scripts.

Official evidence name: Maven Central search API guide and the selected build tool's dependency locking documentation.

## Cargo

Use registry version records with version, creation time, and yanked status. Preserve the `Cargo.toml` requirement and run a precise package update so only the selected lock entry changes.

Official evidence name: registry or crates service version API documentation.

## Go modules

Use `go list` for module versions and retractions, then read the configured module proxy `.info` record for its `Time`. Exclude retracted versions and block unverifiable pseudo-versions.

Run targeted `go get module@version`, then `go mod tidy`. Accept only the expected `go.mod` and `go.sum` changes.

Official evidence name: Go Modules Reference.

## GitHub Actions

Use repository releases with a complete SemVer tag and a release publication time. Reject draft and prerelease entries. A movable major or minor tag such as `v4` or `v4.2` is unverifiable and blocks processing.

Update only to a complete SemVer tag or the immutable commit SHA resolved from that release. Preserve an existing immutable-SHA pin and its version comment.

Official evidence name: GitHub Releases API documentation.
