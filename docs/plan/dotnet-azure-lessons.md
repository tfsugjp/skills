# .NET / Azure Lessons Plugin

## Summary

`dotnet-azure-lessons` turns recurring corrections from past agent sessions into checkable rules for .NET, Azure, and PowerShell work. Eleven skills and a read-only reviewer agent keep the same mistakes from coming back. Tracking: parent Issue #107 with sub-issues #108-#111.

## Design

- Source: redo requests, user corrections, and reviewer, Copilot, and Codex findings from agent sessions in 17 projects, about 70 cases after merging duplicates, then cross-checked against Claude Code and Codex sessions from a second workstation (13 projects), and against Claude Code sessions from a macOS workstation (about 115 sessions in 13 project directories; that machine's Codex history was not read). Each pass added missing lessons, corrected rules the history contradicted, and merged rules that overlapped between skills. Project names, host names, domains, and URLs are generalized and not published.
- Nine skills load in one phase of the work; two load in a situation (work on macOS, and a command that fails because of the agent session). All use the same structure: when not to use, then rules. Every rule has a check and a reason, and each skill ends with one line that says to confirm the applicable checks before reporting done. There is no separate done checklist, because it restated the rules.
- Rules that must hold for every command (for example the shape of commands under permission rules) cannot depend on a skill being triggered. `agent-sandbox-troubleshooting` covers the diagnosis after a failure; standing command rules belong in the user's or repository's agent instructions.
- Skills hand off to existing skills instead of repeating them: `windows-shell-safety` for native command quoting, `github-pull-request` for PR bodies and closing keywords, `github-plan-issues` for issue hierarchies, `azure-devops-pipelines` for pipeline runs, `project-documentation` for ADR and architecture documents, `nuget-validate` for package versions, and `native-container-cli` for container commands. Cross-references between skills name the rule by title, not by number.
- The `dotnet-lessons-reviewer` agent selects the skills that apply to a diff, tests the diff against each rule's check, and reports findings without editing files.

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

- `python scripts/validate_marketplaces.py` checks manifests, skill frontmatter, and relative links.
- A search for URLs and private host names under the plugin directory finds nothing.
- Each description names its phase or the symptoms that trigger it, and each when-not-to-use section names the neighboring skills, so one prompt does not load every skill.
- Not verified: whether each skill loads only in its intended situation in real sessions.
