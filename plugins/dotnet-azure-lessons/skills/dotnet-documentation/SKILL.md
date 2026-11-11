---
name: dotnet-documentation
description: 'Rules for keeping documentation true to the code in .NET and Azure repositories, learned from documentation drift found in review. Use while changing code that adds, renames, or deletes an environment variable, option, command, file, folder, or feature; while editing a README, setup guide, runbook, Wiki page, diagram, API-version table, or XML documentation comment; while writing Azure DNS, custom domain, or download-and-verify procedures; while adding screenshots or evidence files; or before making a repository public.'
---

# .NET Documentation

Documentation problems were rarely style issues. They were statements that stopped being true, or things that were never documented.

## When not to use

- ADR, architecture, infrastructure, test, and setup templates and approval gates: `project-documentation`.
- Publishing a plan to a Wiki: `github-wiki-plan` or `azure-devops-wiki`.
- Scripts inside documentation: the `script-author` agent when available, and `powershell-scripting`.
- What a verification record must contain: `dotnet-testing`, "Record test execution and acceptance gates separately".

## Rules

### 1. Update every companion of a change in the same change

- **Rule:** When code adds an environment variable, setting, command, option, generated file, or supported platform, or the user sets a policy (for example what is not tested and why), update the operational documentation, its index, the README's list of features or skills, and the ADR when one records the decision. When a build command, path, or project changes, update the workflow and pipeline YAML, scripts, and lock or manifest files that name it. When a file or folder is renamed or deleted, search the repository for references to the old path and fix each one.
- **Check:** Each new name appears in the docs with its purpose and default; `git grep` for each old name or path returns nothing.
- **Why:** A new environment variable, a new skill's README entry, workflow YAML after a command change, and a lock file were each left out until the user asked, and eight documents still linked to a deleted folder.

### 2. Make prose, tables, diagrams, XML docs, and help agree with the code

- **Rule:** Compare each `<summary>`, `<returns>`, and `<exception>` with the implementation; update an option's help text, README, and examples together when behavior changes; and check every value in a table (API versions, defaults, supported platforms) and every edge in a diagram against the code. Do not promise logging, exceptions, or isolation the code does not provide.
- **Check:** Documented exceptions, side effects, table values, and diagram edges each match a code path; help output and README agree.
- **Why:** XML comments claimed logging and exceptions that did not exist, a `--dry-run` description went stale, an API-version table said v1.0 where the code used beta, and prose said "the only external call" while the diagram showed a second one.

### 3. Use real dates

- **Rule:** Dates in documents, changelogs, and plans are the current date or the referenced event's date, never future dates.
- **Check:** No date in the change is later than today.
- **Why:** A review flagged future-dated references.

### 4. Write DNS and custom-domain procedures per record type

- **Rule:** For Static Web Apps, App Service, or Front Door custom domains, document the apex domain and each subdomain separately: record type, record name, where to copy the value and validation token from, and what to check when validation stays pending. Use placeholder domains.
- **Check:** Each step was compared with the actual portal or CLI output.
- **Why:** A procedure omitted the validation token source and the apex versus `www` difference, and apex validation never completed.

### 5. Keep names consistent inside snippets

- **Rule:** In copy-and-paste snippets, file names, versions, architectures, and paths agree from first line to last; a download-and-verify snippet saves the file under the same name it looks up in the checksum list. Quote arguments the reader's shell would expand (see `dotnet-macos-development`, "Write shell for zsh and the system tools").
- **Check:** Run the snippet against a real release asset, or trace each name through it.
- **Why:** A README snippet saved a generic file name but searched for the versioned name, so verification never matched.

### 6. Follow the repository's language and placeholder rules

- **Rule:** Write documents in the language the repository requires (for example English with `_ja.md` translations for MIT repositories), keep translated pairs one-to-one, and use placeholders for private URLs, IP addresses, host names, and email addresses. Read the exceptions in the rules before replacing a link: public, unauthenticated URLs such as public issue links are often allowed.
- **Check:** Translated pairs have the same headings, tables, versions, and status; a URL search finds only allowed ones.
- **Why:** Leaked hosts are hard to remove later, and a public issue link was wrongly replaced with a bare number.

### 7. Review images and history before publishing

- **Rule:** Before screenshots or evidence files are committed, and before a repository is made public, look at each image for user names, account details, personal photos, and host names; secret scanners read text and history, not pixels. Run the history scan as well, and report both results separately.
- **Check:** The report lists the images reviewed and the history scan result.
- **Why:** A history scan came back clean while an evidence folder of screenshots still needed a visual check and was removed before the repository went public.

### 8. Reconcile documentation after conflicts

- **Rule:** Compare the resolved document with both sides of a merge, including scope, stage labels, versions, and verification status. Recover garbled text from a known-good revision and reapply the intended edits.
- **Check:** The resolved files read correctly as UTF-8, and translated pairs agree.
- **Why:** Conflict resolution garbled words and left contradictory verification wording in English and Japanese.

## Before reporting done

Confirm each applicable Check above, or state which one was not done.
