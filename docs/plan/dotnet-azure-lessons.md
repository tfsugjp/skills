# .NET / Azure Lessons Plugin

## Summary

`dotnet-azure-lessons` turns demonstrated corrections from agent sessions into scoped, checkable guidance for .NET, Azure, and PowerShell. It contains eleven skills and one read-only reviewer. Tracking: parent Issue #107 and sub-issues #108–#111.

## Design

- Select lessons from observed failures, user corrections, and review findings. Treat unexecuted proposals and static findings as such. Generalize private identifiers; never publish raw sessions, credentials, private paths, or project-specific assumptions.
- Keep each description short and specific to its triggering task or symptom. Load only relevant rules and references. Preserve eleven entry points; do not create additional skills solely to categorize this history pass.
- Retain a concise rule, observable check, and failure rationale for each non-obvious invariant. Remove repeated anecdotes, generic exhortations, duplicate closing checklists, and overlapping procedures. Give each shared invariant one owner and use named cross-references.
- Express applicability and exceptions explicitly. A rule does not authorize external writes, installations, credential resets, settings changes, closing unrelated windows, or expanding the requested work. Reuse existing authorization and follow the current session's permission mechanism; distinguish an approval request from an explicit denial. Prefix-matching command advice applies only to environments with that policy.
- Add missing evidence-backed checks: reassess findings against the current PR head before publication; separate CLI authentication from Git credential helpers; stage and validate environment/profile updates before switching, preserve unowned data, and define recovery after partial failure; distinguish PowerShell source encoding requirements from generated-file encoding.
- Keep technical failure-prevention rules while narrowing overbroad mandates: migration of solution formats only within task scope; package installation and UI validation in an appropriate authorized environment; prerequisite failures distinguished from recoverable warnings; safe package builds distinguished from credentialed publication. Recheck technical claims against owning sources when changing their meaning.
- The reviewer covers committed, staged, and unstaged changes, selects applicable checks, and reports actionable defects separately from missing evidence. It never treats an unavailable screenshot or unrun platform test as proof of a defect and never mutates external records.
- Existing skills own their specialized procedures: `windows-shell-safety`, `github-pull-request`, `github-plan-issues`, `azure-devops-pipelines`, `project-documentation`, `nuget-validate`, and `native-container-cli`. Missing optional skills do not justify claiming their workflow ran.

| Skill | Phase or situation |
|---|---|
| `dotnet-architecture-design` | Design documents, ADRs, version support |
| `dotnet-coding` | C# implementation |
| `vs-extension-remote-ui` | Visual Studio Remote UI view models and XAML |
| `powershell-scripting` | PowerShell scripts |
| `dotnet-debugging` | Failure investigation |
| `dotnet-testing` | Tests and the decision that a change is verified |
| `dotnet-documentation` | Documentation that changes with the code |
| `dotnet-ci-cd` | Workflow and pipeline definitions, packaging |
| `pr-issue-workflow` | Review threads, commits, pushes, merges, issue closure |
| `dotnet-macos-development` | .NET and Azure work on macOS or Apple silicon |
| `agent-sandbox-troubleshooting` | A command fails because of the agent session's sandbox, permissions, or credentials |

## Verification

- Validate marketplace manifests, frontmatter, names, and local links; inspect the final diff and bilingual consistency.
- Check the plugin for leaked source identifiers and secrets. Keep history evidence local rather than publishing source-session excerpts.
- Use independent, read-only scenario evaluation for stale review heads, authentication failures, denied operations, staged changes, partial profile updates, and unavailable platform verification. Check decisions and side effects, not exact wording.
- Separate static validation, simulated scenario outcomes, and actual skill selection in live clients. Do not claim live invocation or platform execution unless observed.
