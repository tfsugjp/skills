---
name: repository-init
description: Initialize repository governance files and persistent project rules once, then record a verified completion marker. Use only when explicitly invoked for first-time repository setup; do not select it for ordinary work or automatic reconfiguration.
---

# Repository initialization

Use this skill only for an explicit `$repository-init` request. It is a one-time repository setup workflow; ordinary implementation, review, or documentation work must not invoke it implicitly.

## Contract

- Work only in the repository root supplied by the user. Do not initialize Git, create a remote, create or update an issue or work item, publish a Wiki page, commit, or push.
- Inspect the repository before changing anything. A missing marker does not prove that the repository is new.
- Use `scripts/init_state.py inspect --root <repository-root>` first. If it reports `complete`, finish without writing. If it reports an invalid or unknown marker, fail without writing. If it reports `in_progress`, resume using the saved license and language profile.
- For a new run, determine the repository's license from existing license files and authoritative project metadata. Preserve a clear existing license. If the license is absent or genuinely ambiguous, ask the user once before creating license-dependent files. For a GitHub repository with no license, offer MIT as the default candidate, but do not create it before the user chooses.
- After the license and profile are known, record the choice with `scripts/init_state.py begin --root <repository-root> --license <license> --profile mit|non-mit`. The helper must reject conflicting choices and must not overwrite an existing marker.

## Files and language policy

Create only missing governance files, unless the user explicitly asks to revise an existing file. Keep existing project-specific rules and merge the reusable rules from [AGENTS.md](assets/AGENTS.md) into a new or existing `AGENTS.md` without deleting custom instructions. If rules conflict, stop and ask the user which rule wins.

For an MIT repository, use the MIT template policy: normal agent responses are Japanese; comments, documentation, and commit messages are English; create Japanese document translations with an `_ja.md` suffix where appropriate. `SECURITY.md` and license-related files remain English and are not translated. For a non-MIT repository, use the non-MIT policy in [AGENTS_non_mit.md](assets/AGENTS_non_mit.md): normal responses, comments, documents, and commit messages are Japanese; do not create `_ja.md` translations; `SECURITY.md` and license-related files remain English.

The files under `assets/` are source templates. `AGENTS_ja.md` is a Japanese reference translation for maintainers and must not be copied beside the generated `AGENTS.md` as an additional executable instruction file. Generate one repository `AGENTS.md` using the selected profile.

If `SECURITY.md` is absent, create it in English using [SECURITY.md](assets/SECURITY.md). Use a placeholder contact and document supported versions from repository evidence; state that support is unconfirmed when evidence is unavailable. Preserve an existing `SECURITY.md`.

## Completion and interruption

Before completion, verify that the selected license policy, `AGENTS.md`, and (when it was missing) `SECURITY.md` are semantically correct, that no unrelated files changed, and that custom instructions were retained. Only then run `scripts/init_state.py complete --root <repository-root>`.

An interrupted run keeps its marker as `in_progress` and keeps already-created files. On resumption, reuse the recorded license and profile and do not replace existing files. A completed run is idempotent: do not rewrite files or marker data. License changes and policy changes are separate explicit tasks.

The helper's marker is `.repository-init.json` with `schema_version: 1`, `status: in_progress|complete`, `license`, and `language_profile: mit|non-mit`. Do not add timestamps, repository URLs, credentials, or other mutable metadata.

## Validation

Run the repository's applicable validation after generation, plus the skill validation and marketplace validation required by the host repository. When scripts are documented, provide both Bash and PowerShell 7 examples; do not add scripts to the target repository unless the user requests them.

For a direct state check, use the equivalent command for the host shell:

```bash
python scripts/init_state.py inspect --root /path/to/repository
python scripts/init_state.py begin --root /path/to/repository --license MIT --profile mit
python scripts/init_state.py complete --root /path/to/repository
```

```powershell
python scripts/init_state.py inspect --root 'C:\path\to\repository'
python scripts/init_state.py begin --root 'C:\path\to\repository' --license MIT --profile mit
python scripts/init_state.py complete --root 'C:\path\to\repository'
```
