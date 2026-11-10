---
name: dotnet-documentation
description: 'Rules for keeping documentation true to the code in .NET and Azure repositories, learned from documentation drift found in review. Use while changing code that adds an environment variable, option, command, file, or feature; while editing a README, setup guide, runbook, Wiki page, or XML documentation comment; while writing Azure DNS, custom domain, or download-and-verify procedures; or when recording verification status. Not for ADR and architecture document structure (project-documentation) or Wiki publishing mechanics (github-wiki-plan, azure-devops-wiki).'
---

# .NET Documentation

Documentation problems were rarely style issues. They were statements that stopped being true, or new things that were never documented.

## When not to use

- ADR, architecture, infrastructure, test, and setup templates and approval gates: `project-documentation`.
- Publishing a plan to a Wiki: `github-wiki-plan` or `azure-devops-wiki`.
- Scripts inside documentation: the `script-author` agent when available, and `powershell-scripting`.

## Rules

### 1. Document new things in the same change

- **Rule:** When code adds an environment variable, setting, command, option, generated file, or supported platform, or the user sets a policy (for example what is not tested and why), update the operational documentation, its index, and the ADR when one records the decision, in the same change.
- **Check:** Each new name appears in the docs with its purpose and default.
- **Why:** A new environment variable, document, and supported OS version, and a test-scope policy, were each missing from README or ADR until the user asked.

### 2. XML documentation and option help describe only what the code does

- **Rule:** Compare each `<summary>`, `<returns>`, and `<exception>` with the implementation, and update an option's help text, README, and examples together when its behavior changes. Do not promise logging or exceptions the code does not perform.
- **Check:** Documented exceptions and side effects match the code paths; help output and README agree.
- **Why:** XML comments claimed every target was logged and malformed values threw; a `--dry-run` description no longer matched.

### 3. Use real dates

- **Rule:** Dates in documents, changelogs, and plans are the current date or the referenced event's date, never future dates.
- **Why:** A review flagged future-dated references.

### 4. Write DNS and custom-domain procedures per record type

- **Rule:** For Static Web Apps, App Service, or Front Door custom domains, document the apex domain and each subdomain separately: record type, record name, where to copy the value and validation token from, and what to check when validation stays pending. Use placeholder domains.
- **Check:** Each step was compared with the actual portal or CLI output.
- **Why:** A procedure omitted the validation token source and the apex versus `www` difference, and apex validation never completed.

### 5. Keep names consistent inside snippets

- **Rule:** In copy-and-paste snippets, file names, versions, architectures, and paths agree from first line to last; a download-and-verify snippet saves the file under the same name it looks up in the checksum list.
- **Check:** Run the snippet against a real release asset, or trace each name through it.
- **Why:** A README snippet saved a generic file name but searched for the versioned name, so verification never matched.

### 6. Record verification honestly

- **Rule:** Tie each verification claim to the commit or artifact, configuration, environment, and observed result. Attribute user verification to the person and what they exercised. Append later acceptance evidence to the condition it satisfies and keep the original skips and blocked gates.
- **Why:** Later user acceptance covered a real-host condition while an earlier evidence gate stayed blocked.

### 7. Follow the repository's language and placeholder rules

- **Rule:** Write documents in the language the repository requires (for example English with `_ja.md` translations for MIT repositories), keep translated pairs one-to-one, and use placeholders for private URLs, IP addresses, host names, and email addresses. Read the exceptions in the rules before replacing a link: public, unauthenticated URLs such as public issue links are often allowed.
- **Check:** Translated pairs have the same headings, tables, versions, and status; a URL search finds only allowed ones.
- **Why:** Leaked hosts are hard to remove later, and a public issue link was wrongly replaced with a bare number.

### 8. Reconcile documentation after conflicts

- **Rule:** Compare the resolved document with both sides of a merge, including scope, stage labels, versions, and verification status. Recover garbled text from a known-good revision and reapply the intended edits.
- **Check:** Read the resolved files as UTF-8; translated pairs agree.
- **Why:** Conflict resolution garbled words and left contradictory verification wording in English and Japanese.

## Done checklist

- [ ] Every new name is documented and indexed.
- [ ] XML documentation, option help, README, and examples match the implementation.
- [ ] No future dates.
- [ ] DNS procedures separate apex and subdomains and show where values come from.
- [ ] Snippets use consistent names.
- [ ] Verification claims have sources.
- [ ] Language, translation pairs, and placeholders follow repository rules.
- [ ] Resolved conflicts keep both sides' intended changes.
