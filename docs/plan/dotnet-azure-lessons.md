# .NET / Azure Lessons Plugin

## Summary

`dotnet-azure-lessons` turns recurring corrections from past agent sessions into checkable rules for .NET, Azure, and PowerShell work. Nine phase-specific skills and a read-only reviewer agent keep the same mistakes from coming back. Tracking: parent Issue #107 with sub-issues #108-#111.

## Design

- Source: redo requests, user corrections, and reviewer, Copilot, and Codex findings from agent sessions in 17 projects, about 70 cases after merging duplicates. Project names, host names, domains, and URLs are generalized and not published.
- Each skill loads in one phase of the work and uses the same structure: when to use, when not to use, rules (rule, check, reason), and a done checklist.
- Skills hand off to existing skills instead of repeating them: `windows-shell-safety` for native command quoting, `github-pull-request` for PR bodies and closing keywords, `github-plan-issues` for issue hierarchies, `azure-devops-pipelines` for pipeline runs, `project-documentation` for ADR and architecture documents, and `nuget-validate` for package versions.
- The `dotnet-lessons-reviewer` agent selects the skills that apply to a diff, checks the diff against their done checklists, and reports findings without editing files.

| Skill | Phase |
|---|---|
| `dotnet-architecture-design` | Design documents, ADRs, version support |
| `dotnet-coding` | C# implementation |
| `vs-extension-remote-ui` | Visual Studio Remote UI view models and XAML |
| `powershell-scripting` | PowerShell scripts |
| `dotnet-debugging` | Failure investigation |
| `dotnet-testing` | Tests and the decision that a change is verified |
| `dotnet-documentation` | Documentation that changes with the code |
| `dotnet-ci-cd` | Workflow and pipeline definitions, packaging |
| `pr-issue-workflow` | Review threads, commits, merges, issue closure |

## Verification

- `python scripts/validate_marketplaces.py` checks manifests, skill frontmatter, and relative links.
- A search for URLs and private host names under the plugin directory finds nothing.
- Each description names its phase and distinctive terms, and each when-not-to-use section names the neighboring skills, so one prompt does not load every skill.
