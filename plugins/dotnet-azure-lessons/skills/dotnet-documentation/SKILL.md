---
name: dotnet-documentation
description: 'Keep .NET and Azure documentation aligned with changed settings, commands, paths, API contracts, and verification evidence. Use when reviewing companion docs, translations, diagrams, setup procedures, or screenshots for publication.'
---

# .NET Documentation

Check claims affected by the change; do not expand a focused edit into a repository-wide rewrite.

## When not to use

- ADR, architecture, infrastructure, test, and setup templates and approval gates: `project-documentation`.
- Publishing a plan to a Wiki: `github-wiki-plan` or `azure-devops-wiki`.
- Scripts inside documentation: the `script-author` agent when available, and `powershell-scripting`.
- What a verification record must contain: `dotnet-testing`, "Record test execution and acceptance gates separately".

## Rules

### 1. Update every companion of a change in the same change

- **Rule:** Trace a changed setting, command, platform, or path to the docs, indexes, workflows, scripts, and manifests that describe or consume it. Update those companions within the authorized scope and applicable documentation approval process. Preserve historical references that intentionally describe an earlier state.
- **Check:** New settings have purpose and defaults; old-name matches are either updated or justified historical references.
- **Why:** Renames left broken links and stale build commands; new settings were unusable without documentation.

### 2. Make prose, tables, diagrams, XML docs, and help agree with the code

- **Rule:** Compare affected XML documentation, help text, examples, table values, and diagram edges with actual code paths. Do not promise logging, exceptions, API versions, or isolation that the implementation does not provide.
- **Check:** Documented exceptions, side effects, table values, and diagram edges each match a code path; help output and README agree.
- **Why:** Documentation promised nonexistent behavior and contradicted the implementation's API version and external calls.

### 3. Use real dates

- **Rule:** Use the actual event date for completed work and source verification. Label future schedules as planned; do not present them as completed events.
- **Check:** Each date agrees with the evidence and its stated status.
- **Why:** Future-dated records misrepresented when work or source verification happened.

### 4. Write DNS and custom-domain procedures per record type

- **Rule:** For Static Web Apps, App Service, or Front Door custom domains, document the apex domain and each subdomain separately: record type, record name, where to copy the value and validation token from, and what to check when validation stays pending. Use placeholder domains.
- **Check:** Each record's value source and pending-validation diagnosis are checked against current official guidance or observed output; unexecuted setup remains unverified.
- **Why:** A procedure omitted the validation token source and the apex versus `www` difference, and apex validation never completed.

### 5. Keep names consistent inside snippets

- **Rule:** In copy-and-paste snippets, file names, versions, architectures, and paths agree from first line to last; a download-and-verify snippet saves the file under the same name it looks up in the checksum list. Quote arguments the reader's shell would expand (see `dotnet-macos-development`, "Write commands for the shell and system tools that run them").
- **Check:** Run the snippet against a real release asset, or trace each name through it.
- **Why:** A README snippet saved a generic file name but searched for the versioned name, so verification never matched.

### 6. Follow the repository's language and placeholder rules

- **Rule:** Write documents in the language the repository requires (for example English with `_ja.md` translations for MIT repositories), keep translated pairs one-to-one, and use placeholders for private URLs, IP addresses, host names, and email addresses. Read the exceptions in the rules before replacing a link: public, unauthenticated URLs such as public issue links are often allowed.
- **Check:** Translated pairs have the same headings, tables, versions, and status; a URL search finds only allowed ones.
- **Why:** Leaked hosts are hard to remove later, and a public issue link was wrongly replaced with a bare number.

### 7. Review images and history before publishing

- **Rule:** Inspect images being published for identifying or secret information; a text scan is not proof that pixels are safe. For a requested transition to a public repository, also inspect relevant tracked history. Keep raw session evidence local and publish only generalized lessons.
- **Check:** Report visual inspection separately from any text/history scan, and identify what was not inspected.
- **Why:** A clean history scan did not establish that screenshots were safe to publish.

### 8. Reconcile documentation after conflicts

- **Rule:** Compare the resolved document with both sides of a merge, including scope, stage labels, versions, and verification status. Recover garbled text from a known-good revision and reapply the intended edits.
- **Check:** The resolved files read correctly as UTF-8, and translated pairs agree.
- **Why:** Conflict resolution garbled words and left contradictory verification wording in English and Japanese.
