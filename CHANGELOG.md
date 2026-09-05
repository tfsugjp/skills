# Changelog

## 0.4.0

- Updated the `relaypublisher-manifest` plugin for Relaypublisher v1.1.0: added Windows `Detection.Type: file` (file-system detection) authoring and static validation, alongside the existing `Detection.Type: script`.
- Removed macOS `Detection.PrimaryBundleId` and `IncludedApps[].BundleBuildVersion` guidance and checks — neither field exists in Relaypublisher v1.1.0's manifest model; the bundled checker now rejects both as unsupported fields. The primary bundle is always `IncludedApps[0]`.
- Added macOS `Detection.IgnoreAppVersion` authoring guidance.
- Added and updated bundled-checker fixtures and unit tests to match the v1.1.0 contract.

## 0.3.0

- Added the `relaypublisher-manifest` plugin for manifest authoring and static validation.
- Added multi-bundle macOS PKG and LOB primary detection guidance.
- Added Windows Win32 manifest authoring and validation guidance (Package/Install/Detection, and the source-item shape shared with macOS `Source`).
- Added a bundled, CLI-independent manifest checker covering both platforms, with unit tests and fixtures, and a CI job that runs every plugin's test suite.
- Added `Assignments`, `Categories`, and macOS pre/post-install `Scripts` authoring and validation guidance, shared between Windows and macOS where the target schema shares the field.
- Added synchronized Claude/Copilot, Codex, and bilingual marketplace documentation.
- Fixed GitHub Wiki Home and verification links to use flattened public page routes.
- Added collision guidance and English/Japanese Wiki template-link regression tests.

## 0.2.0

- Hardened Azure Boards Work Item registration for non-English Windows with native PowerShell and UTF-8 read-back verification.
- Added mandatory Azure DevOps Wiki handoff and verification for Feature-equivalent Work Items.
- Synchronized Codex, Claude, and GitHub Copilot plugin metadata and mirrors.

## 0.1.0

- Added the `azure-devops-toolkit` plugin bundle.
- Added the `nuget-validate` plugin bundle.
- Added Claude Code and GitHub Copilot marketplace metadata.
- Added the Codex repository-local marketplace metadata.
- Added marketplace validation and GitHub Actions checks.
