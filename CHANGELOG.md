# Changelog

## 0.3.0

- Added the `relaypublisher-manifest` plugin for manifest authoring and static validation.
- Added multi-bundle macOS PKG and LOB primary detection guidance.
- Added Windows Win32 manifest authoring and validation guidance (Package/Install/Detection, and the source-item shape shared with macOS `Source`).
- Added a bundled, CLI-independent manifest checker covering both platforms, with unit tests and fixtures, and a CI job that runs every plugin's test suite.
- Added `Assignments`, `Categories`, and macOS pre/post-install `Scripts` authoring and validation guidance, shared between Windows and macOS where the target schema shares the field.
- Added synchronized Claude/Copilot, Codex, and bilingual marketplace documentation.

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
