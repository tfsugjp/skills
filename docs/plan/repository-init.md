# Repository Init Plugin

## Summary

`repository-init` is an explicitly invoked, one-time workflow for new and existing repositories. It separates first-run decisions from rules that must remain in `AGENTS.md` for every later task.

## Design

- Inspect the target root before changing it. A missing record is not evidence that the repository is new.
- Detect and preserve a clear existing license. Ask once when the license is absent or ambiguous; do not create a license before the choice is settled.
- Create only missing governance files: `AGENTS.md`, and an English `SECURITY.md` when it is absent. Preserve existing project-specific rules and stop on rule conflicts.
- Store only `schema_version`, `status`, `license`, and `language_profile` in `.repository-init.json`. Use `in_progress` for interruption and `complete` only after semantic verification.
- Reject invalid records and conflicting decisions without overwriting them. Completed runs perform no writes.
- Do not initialize Git, create remotes, create issues or work items, publish Wiki pages, commit, or push.

## Language profiles

MIT repositories use Japanese agent responses, English comments, documents, and commits, plus `_ja.md` translations where needed. Non-MIT repositories use Japanese comments, documents, and commits without `_ja.md` translations. Security and license files remain English in both profiles.

## Verification

The helper state transitions are covered by unit tests for missing, in-progress, complete, interrupted, conflicting, malformed, locked, atomic-write failure, and repeat-invocation cases. Marketplace metadata and relative skill links are checked by the repository validator.
