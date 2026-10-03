# Azure DevOps Wiki Repository Hierarchy

[日本語](https://github.com/tfsugjp/skills/wiki/azure-devops-wiki-repository-hierarchy_ja)

## Summary

Make the `azure-devops-wiki` skill publish plans and bug fix plans into one fixed, repository-rooted hierarchy. The repository root page holds the repository overview and the current overall design, and every specification change updates it. `plan` and `bug` index pages list every child page with its Work Item, pull request, status, and summary.

## Tracking

| Type | Issue |
|---|---|
| Parent | [Issue #73](https://github.com/tfsugjp/skills/issues/73) |
| Sub-issue | [Issue #74](https://github.com/tfsugjp/skills/issues/74) |
| Sub-issue | [Issue #75](https://github.com/tfsugjp/skills/issues/75) |
| Sub-issue | [Issue #76](https://github.com/tfsugjp/skills/issues/76) |
| Sub-issue | [Issue #77](https://github.com/tfsugjp/skills/issues/77) |

## Background

Existing Azure DevOps wikis mix several shapes: a `<repo>-plan` page that holds the design with plans directly beneath it, a repository page with an overview table but no design, plan indexes without a PR column, and indexes that miss child pages. Pull requests were sometimes written as `#<n>`, which Azure DevOps Wiki renders as a Work Item reference. The skill also forbade creating Wiki structure, so these gaps could not be repaired through the skill.

## Design

- Fixed layout: `/<repo>` (overview table and overall design), `/<repo>/plan` and `/<repo>/bug` (indexes), and `/<repo>/plan/<id>-<slug>` and `/<repo>/bug/<id>-<slug>` (child pages named by Work Item ID).
- Root page: overview rows for repository, default branch, infrastructure (CLIs, Azure PaaS, IaC entry point), build outputs, CI/CD with definition links, and design documents, followed by the final-form overall design. A plan or bug fix that changes the specification updates the root in the same publish.
- Index pages: one table with Work Item, Page, PR, Status, and Summary columns that lists every existing child page.
- Plan and bug templates: a metadata table with Work Item, branch, PR, and status, then the plan sections, or symptoms, root cause, fix approach, and verification. A bug page is created when the fix approach for a Bug is approved, and the PR row is filled in after the PR exists.
- Pull requests are links whose text starts with `!`; wiki pages link with standard Markdown links so page moves can repair them. Page prose follows the existing wiki's language.
- Non-conforming pages are detected, a mapping is proposed, and pages are moved with the page move API only after user approval. Pages are never deleted.
- The Boards skill and Work Item agent hand approved plans and Bug fix plans to the Wiki skill and leave structure creation to its publish sequence.

## Implementation

1. Add the hierarchy, publish sequence, migration procedure, and four templates to the `azure-devops-wiki` skill.
2. Add `--require-pr` and `--require-page-link` checks to the Python and PowerShell validators, with unit tests that cover templates and PowerShell parity.
3. Update the Boards skill and Work Item agent handoff, including the Bug fix plan registration.
4. Synchronize `.github` mirrors, CHANGELOG (English and Japanese), and the plugin version 0.3.0.

## Verification

- Run the validator unit tests, including PowerShell 7 parity, and the marketplace validator.
- Check byte-for-byte mirror equality between `plugins/azure-devops-toolkit` and `.github`.
- Render each template with sample values and confirm it passes the validator with its required Work Item, PR, and page links.
