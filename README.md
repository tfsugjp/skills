# TFSUG.JP Agent Skills

Personal plugins for Azure DevOps, GitHub, .NET package maintenance, Relaypublisher, and Windows shell-safe command execution workflows (skills + agents). The repository is structured so the same plugin content can be tested with Claude Code, GitHub Copilot, and Codex.

## Plugins

| Plugin | Included skills and agents |
|---|---|
| `azure-devops-toolkit` | Skills: Azure DevOps Foundation, Boards, Repos, Pipelines, Artifacts, Test Plans, Wikis, Advanced Security, CLI, security triage. Boards uses native PowerShell on Windows, writes body fields as Markdown, records the root cause and fix approach in a Bug's Repro Steps, links work items back to their Wiki pages, and Feature-equivalent Work Items and approved Bug fix plans require Wiki traceability. Wikis publishes plans and bug fix plans under a repository-rooted hierarchy (`/<repo>` overall design, `/<repo>/plan` and `/<repo>/bug` indexes) with bundled page templates and validators. Agents: Azure DevOps Agent, Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet vulnerability, deprecation, listing, freshness, and project-audit validation |
| `dependabot-safe-merge` | Safe Dependabot refresh, release-age policy, merge gates, and major-upgrade planning |
| `github-plan-wiki` | Skills: GitHub Plan Issues (parent + sub-issue hierarchy via `gh`), GitHub Wiki Plan (bilingual GitHub wiki publishing and Home index maintenance) |
| `relaypublisher-manifest` | Relaypublisher manifest creation, updates, and static validation for v1.1.0, including Windows Win32 script/file-system detection and multi-bundle macOS PKG/LOB detection |
| `repository-init` | Explicit repository initialization for license, security, language rules, and `AGENTS.md` guidance |
| `windows-shell-safety` | Windows-safe Azure CLI, JSON, and pipe execution: rules against `cmd.exe` argument loss, a pre-execution lint (`Test-NativeCommand.ps1`), and a PowerShell 7 helper that sends JSON through UTF-8 `@<file>` |

All plugins are distributed under the MIT License. The plugin bundles contain no credentials and do not configure an MCP server automatically. Azure DevOps authentication and permissions remain the responsibility of the user.

## Install from the Claude Code marketplace

Add the repository as a marketplace, then install the plugin you need:

```text
claude plugin marketplace add tfsugjp/skills
claude plugin install azure-devops-toolkit@tfsugjp-agent-skills
claude plugin install nuget-validate@tfsugjp-agent-skills
claude plugin install dependabot-safe-merge@tfsugjp-agent-skills
claude plugin install github-plan-wiki@tfsugjp-agent-skills
claude plugin install relaypublisher-manifest@tfsugjp-agent-skills
claude plugin install repository-init@tfsugjp-agent-skills
claude plugin install windows-shell-safety@tfsugjp-agent-skills
```

## Install from the GitHub Copilot marketplace

The Copilot CLI reads the shared Claude marketplace catalog in this repository:

```text
copilot plugin marketplace add tfsugjp/skills
copilot plugin install azure-devops-toolkit@tfsugjp-agent-skills
copilot plugin install nuget-validate@tfsugjp-agent-skills
copilot plugin install dependabot-safe-merge@tfsugjp-agent-skills
copilot plugin install github-plan-wiki@tfsugjp-agent-skills
copilot plugin install relaypublisher-manifest@tfsugjp-agent-skills
copilot plugin install repository-init@tfsugjp-agent-skills
copilot plugin install windows-shell-safety@tfsugjp-agent-skills
```

## Install from the Codex repository-local marketplace

Set `REPO_ROOT` to the checked-out repository directory. Codex uses the repository-local catalog under `.agents/plugins/`:

```text
codex plugin marketplace add "$REPO_ROOT"
codex plugin add azure-devops-toolkit@tfsugjp-agent-skills
codex plugin add nuget-validate@tfsugjp-agent-skills
codex plugin add dependabot-safe-merge@tfsugjp-agent-skills
codex plugin add github-plan-wiki@tfsugjp-agent-skills
codex plugin add relaypublisher-manifest@tfsugjp-agent-skills
codex plugin add repository-init@tfsugjp-agent-skills
codex plugin add windows-shell-safety@tfsugjp-agent-skills
```

Use `repository-init` only with an explicit `$repository-init` request. It initializes missing governance files in a new or existing repository, records the resolved license and language profile in `.repository-init.json`, and leaves a completed repository unchanged on later invocations. It does not initialize Git, create remotes, create issues or work items, publish Wiki pages, commit, or push.

The Codex local marketplace is intended for development and team distribution. Public Codex listing submission is a separate release step after the plugins pass validation.

## Windows Shell Safety

`windows-shell-safety` is for agents (and people) running Azure CLI and other native commands on Windows. `az` is the batch file `az.cmd`, so its arguments are parsed by PowerShell and then by `cmd.exe`: unquoted `|`, `&`, `<`, `>`, `^` are consumed, `%VAR%` is expanded, and double quotes inside inline JSON are stripped. Retrying with different escaping wastes time; the skill prescribes one safe path instead.

- Rules: use `pwsh` only, run scripts with `pwsh -File` instead of `-Command` strings, pass JSON through a UTF-8 file as `'@<file>'`, filter `az` output with `ConvertFrom-Json` (or load `--query` from `'@<file>'`), and set UTF-8 console encoding before parsing native output.
- Lint before running: `Test-NativeCommand.ps1` reports rules WSS001-WSS009 (for example `cmd.exe`, nested `-Command`, `cmd` metacharacters or inline JSON passed to `az`, unquoted `@file`) with the reason and the safe rewrite, and exits with 1 when it finds anything.
- Helper: dot-source `Invoke-NativeJson.ps1` for `Invoke-AzJson` / `Invoke-NativeJson` (UTF-8 body file, parsed JSON output, `-Raw` for text output, refusal of arguments `cmd.exe` would rewrite) and `-EchoArgs` / `Show-NativeArgs` to see the argv a `.cmd` target actually receives.

```powershell
$skill = 'plugins/windows-shell-safety/skills/windows-shell-safety'
pwsh -NoProfile -File "$skill/scripts/Test-NativeCommand.ps1" -Command 'az version --query "keys(@)|[0]" -o tsv'
. "$skill/scripts/Invoke-NativeJson.ps1"
(Invoke-AzJson -Arguments 'version').'azure-cli'
```

The skill is advisory: it ships no hook, so lint findings never block a tool call on their own.

## Project Documentation

The [project-documentation skill](.github/skills/project-documentation/SKILL.md) creates English project records organized under `docs/adr/`, `docs/architecture/`, `docs/infra/`, `docs/test/e2e/`, and `docs/setup/`. It requires explicit approval before changing existing records, retains reasons and history for in-place decision updates, and records architecture rationale URLs and actual E2E evidence.

### Installation and Use

This repository already places the English skill in the project discovery directory. To use it in another repository, copy the entire `.github/skills/project-documentation/` folder, including its MIT license and templates, into that repository's `.github/skills/` directory. Use a compatible agent client and request project documentation; the client determines discovery and activation.

Example requests:

- “Document the current architecture and its decision rationale under docs/.”
- “Draft an update to ADR 0001, show the exact diff and reason, and wait for my approval.”
- “Document the checkout E2E scenario, distinguishing the test plan from actual run evidence.”

### Resources

- [English skill](.github/skills/project-documentation/SKILL.md)
- [ADR template](.github/skills/project-documentation/templates/adr/decision.md)
- [Architecture template](.github/skills/project-documentation/templates/architecture/design.md)
- [Infrastructure template](.github/skills/project-documentation/templates/infra/runbook.md)
- [Test strategy template](.github/skills/project-documentation/templates/test/strategy.md)
- [E2E template](.github/skills/project-documentation/templates/test/e2e/scenario.md)
- [Setup template](.github/skills/project-documentation/templates/setup/guide.md)

The [Japanese reference translation](docs/skill-guides/project-documentation_ja.md) is for human readers only. It has no skill frontmatter, is not registered, and must not be copied into any skill discovery directory or used as authoritative agent input. English instructions are authoritative. Templates are scaffolds, not evidence that project decisions or tests already exist.

## Development validation

Run the repository validator from the repository root:

```text
python scripts/validate_marketplaces.py
python -m unittest discover -s plugins/github-plan-wiki/skills/github-wiki-plan/tests -p 'test_*.py'
```

The validators check JSON syntax, matching plugin names and versions, skill frontmatter, source paths, relative links, plugin-root boundaries, and flattened GitHub Wiki template routes. The same checks run in GitHub Actions for pushes to `main` and pull requests. The `tests` job also runs every plugin's `tests/test_*.py` (the `windows-shell-safety` tests need `pwsh`), and the `windows-shell-safety` job on `windows-latest` reproduces the `cmd.exe` argument loss and verifies the safe patterns.

When editing a plugin during local Codex development, refresh the local installation after changing the manifest and start a new conversation to pick up the updated skills.

## License

MIT. See [LICENSE](LICENSE) and the copy included in each plugin bundle.

The project-documentation skill includes its own [MIT license copy](.github/skills/project-documentation/LICENSE.txt). See [SECURITY.md](SECURITY.md) for vulnerability reporting guidance.

[Japanese overview](README_ja.md)
