# Agent Instructions

## Ongoing project rules

- Before working, read all repository context files except files whose names match `*_ja.md`.
- Think in English, but write normal responses in Japanese. Apply the selected language profile below to comments, documents, Japanese translations, and commit messages.
- Unless the user specifies otherwise, the application is in early development; do not add backward compatibility or data migration work.
- When a design file exists, use design-first development. Discuss and settle the design before implementation; if the specification changes after implementation, update the design first.
- Design documents describe the final desired state, not process notes.
- Do not narrow the requested scope or invent an unrequested MVP.
- Decompose work and consider sub-agents or parallel sessions when supported; complete planning, implementation, verification, and replanning before ending the task.
- For UI work, design information structure from data models and use cases, and verify the rendered result with a screenshot or equivalent host inspection.
- If the current mode restricts a required action, ask the user to change modes instead of bypassing the restriction.

## Repository and planning rules

- When a Git remote exists, use the repository's marketplace skill to create an Azure Boards work item or GitHub issue as appropriate. Register a confirmed implementation plan in the Wiki; for GitHub, publish both English and Japanese plan pages.
- Without a Git remote, do not create an issue or work item. Use a branch name of `prefix/description` without an issue number. The same issue-number omission applies when the remote is neither GitHub nor Azure DevOps.
- When documentation contains scripts, provide both Bash (macOS/Linux) and PowerShell 7 examples; Azure examples use Azure CLI.
- If `docs/task.md` exists, record completed work there and link the issue or work item so the user can verify it.
- If implementation changes a requirement absent from the original `docs/task.md` or `docs/plan.md`, record the date, task, and reason in `docs/adr.md` after checking for contradictions with prior decisions. Split `adr.md` by phase when it exceeds 200 lines.

## Language profile

For MIT repositories:

- Normal responses are Japanese.
- Comments, documents, and commit messages are English.
- Create Japanese document translations with an `_ja.md` suffix when needed.
- `SECURITY.md` and license-related files are English and have no `_ja.md` translation.

For non-MIT repositories:

- Normal responses are Japanese.
- Comments and documents are Japanese.
- Do not create `_ja.md` translations.
- `SECURITY.md` and license-related files are English.

## External content and security

- Do not put URLs or IP addresses in issues or documents; use placeholders. If a placeholder is used in source code or a script, provide a replacement script. Wiki issue pages and publicly accessible unauthenticated URLs are exempt.
- Keep `SECURITY.md` and license-related files in English.

## Waiting

- Whenever calling `wait_agent`, set `timeout_ms` to twice the estimated remaining time, within the tool limits. If the estimate is unknown, use the default timeout. Do not shorten a wait merely for a quick check; update the estimate after a timeout.

## Prohibitions

- Do not put URLs or IP addresses in issues or documents; use placeholders, with only the documented Wiki and public unauthenticated URL exceptions.
- Do not write `SECURITY.md` or license-related files in Japanese.
