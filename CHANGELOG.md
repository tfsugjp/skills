# Changelog

## Unreleased

- Updated `azure-devops-toolkit` to 0.3.1: the `azure-devops-boards` skill writes body fields as Markdown by switching the field with `/multilineFieldsFormat/<field>` (MCP `format: "Markdown"`) and falls back to HTML only when the server does not support Markdown fields, with format-aware read-back checks. Verified against Azure DevOps Services: `<` is encoded as `&amp;lt;` in prose and `&lt;` in code, because the server strips tag-shaped text and the form preview decodes the value once (a single `&lt;script&gt;`, as the MCP server sends, hid the rest of the body).
- Bugs now record the AI's Root cause and Fix approach, together with Repro steps and Expected vs actual, in Repro Steps, which is the body field the Bug form shows. The Work Item agent follows the same rule.
- Work items of any type whose content is registered in the Azure DevOps Wiki are linked back to the page with a `## Wiki` body section and a `Hyperlink` relation; the `azure-devops-wiki` skill returns the page `remoteUrl` for this. The Windows-native reference adds tested `Write-WorkItemBody` and `Add-WikiBackLink` PowerShell helpers and Linux/macOS equivalents. The `azure-devops-cli` and `azure-devops-security-triage` skills now defer work item bodies to the same rules.
- Updated `azure-devops-toolkit` to 0.3.0: the `azure-devops-wiki` skill now publishes into a repository-rooted hierarchy (`/<repo>` overview and overall design, `/<repo>/plan` and `/<repo>/bug` indexes), with root, index, plan, and bug fix plan templates, required Work Item and pull request references, and an approval-gated migration procedure for non-conforming pages.
- Added `--require-pr` / `-RequirePr` and `--require-page-link` / `-RequirePageLink` checks to the Wiki validators, with unit tests that also verify PowerShell parity.
- The Boards skill and Work Item agent now hand approved Bug fix plans to the Wiki skill and delegate Wiki structure creation to its publish sequence.
- Added the explicitly invoked `repository-init` plugin for one-time repository governance setup with resumable, idempotent state tracking.

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
