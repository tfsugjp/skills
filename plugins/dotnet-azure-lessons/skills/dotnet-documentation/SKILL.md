---
name: dotnet-documentation
description: 'Rules for keeping documentation true to the code in .NET and Azure repositories, learned from documentation drift found in review. Use while changing code that adds an environment variable, option, command, file, or feature; while editing a README, setup guide, runbook, Wiki page, or XML documentation comment; while writing Azure DNS, custom domain, or download-and-verify procedures; or when recording verification status. Not for ADR and architecture document structure (project-documentation) or Wiki publishing mechanics (github-wiki-plan, azure-devops-wiki).'
---

# .NET Documentation

Documentation problems in past sessions were rarely style issues. They were statements that stopped being true, or new things that were never documented.

## When not to use

- ADR, architecture, infrastructure, test, and setup document templates and approval gates: use `project-documentation`.
- Publishing a plan to a Wiki: use `github-wiki-plan` or `azure-devops-wiki`.
- Scripts inside documentation: delegate to the `script-author` agent when it is available, and follow `powershell-scripting`.

## Rules

### 1. Document new things in the same change

- **Rule:** When code adds an environment variable, setting, command, option, generated file, or supported platform, update the operational documentation and its index or table of contents in the same change.
- **Check:** Search the docs for each new name; every one appears with its purpose and default.
- **Why:** A new environment variable, a new document, and a new supported OS version were each missing from the documentation until a user or reviewer asked.

### 2. XML documentation describes only what the code does

- **Rule:** Compare each `<summary>`, `<returns>`, `<exception>`, and logging statement in XML documentation with the implementation. Do not promise behavior (logging each item, throwing on bad input) that the code does not perform.
- **Check:** For each changed member, the documented exceptions and side effects match the code paths.
- **Why:** XML comments claimed every target was logged and that malformed values threw; neither was true.

### 3. Keep option descriptions in sync with behavior

- **Rule:** When a command option changes (for example `--dry-run`), update its help text, README, and examples together.
- **Check:** The help output and the README describe the same behavior.
- **Why:** A dry-run description no longer matched the implementation.

### 4. Use real dates

- **Rule:** Dates in documents, changelogs, and plans are the actual current date or the date of the referenced event. Never write future dates.
- **Check:** Compare each new date with today.
- **Why:** A review flagged future-dated references.

### 5. Write DNS and custom-domain procedures per record type

- **Rule:** For Azure Static Web Apps, App Service, or Front Door custom domains, document the apex domain and each subdomain separately: record type, record name, the value to copy from the portal or CLI, and how to read the validation token. Include what to check when validation stays pending. Use placeholders for domains.
- **Check:** Each step was compared with the actual portal or CLI output.
- **Why:** A procedure did not show where to get the validation token or how apex and `www` records differ, and apex validation never completed.

### 6. Check names and paths inside snippets

- **Rule:** In copy-and-paste snippets, file names, versions, architectures, and paths are consistent from the first line to the last.
- **Check:** Run the snippet, or trace each name through it.
- **Why:** A verification snippet saved one file name and searched for another.

### 7. Record verification honestly

- **Rule:** Tie verification to the commit or artifact, configuration, environment, and observed result. Attribute user verification to the person and what they exercised. Append later acceptance evidence to the condition it satisfies and retain the original skips, blocked gates, or checks that never started.
- **Check:** Each verification claim traces to evidence for that target. A harness result and real-host acceptance have separate entries when both matter.
- **Why:** Later user acceptance covered a real-host condition while the earlier evidence gate remained blocked.

### 8. Follow the repository's language and placeholder rules

- **Rule:** Write documents in the language the repository requires (for example English with `_ja.md` translations for MIT repositories), keep translated pairs one-to-one, and use placeholders instead of real URLs, IP addresses, host names, and email addresses, except where the repository rules allow them.
- **Check:** Translated pairs have the same headings and tables; a search for URLs finds only allowed ones.
- **Why:** Repository rules require it, and leaked hosts are hard to remove later.

### 9. Reconcile documentation after conflicts

- **Rule:** Compare the resolved document with both sides of a merge. Check scope, stage labels, versions, and verification status. If text is garbled, recover the affected text from a known-good revision and reapply the intended edits.
- **Check:** Read the resolved files as UTF-8. For translated pairs, verify that versions, conditions, and completion status agree as well as headings and tables.
- **Why:** Conflict resolution garbled words and left contradictory verification-stage wording in English and Japanese.

## Done checklist

- [ ] Every new name is documented and indexed.
- [ ] XML documentation matches the implementation.
- [ ] Option help, README, and examples agree.
- [ ] No future dates.
- [ ] DNS procedures separate apex and subdomains and show where values come from.
- [ ] Snippets use consistent names.
- [ ] Verified marks have sources.
- [ ] Language, translation pairs, and placeholders follow repository rules.
- [ ] Resolved documentation conflicts preserve both sides' intended changes and matching verification status.
