# TFSUG.JP Agent Skills

Personal plugins for Azure DevOps, GitHub, .NET package maintenance, and Relaypublisher workflows (skills + agents). The repository is structured so the same plugin content can be tested with Claude Code, GitHub Copilot, and Codex.

## Plugins

| Plugin | Included skills and agents |
|---|---|
| `azure-devops-toolkit` | Skills: Azure DevOps Foundation, Boards, Repos, Pipelines, Artifacts, Test Plans, Wikis, Advanced Security, CLI, security triage. Boards uses native PowerShell on Windows and Feature-equivalent Work Items require Wiki traceability. Agents: Azure DevOps Agent, Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet vulnerability, deprecation, listing, freshness, and project-audit validation |
| `dependabot-safe-merge` | Safe Dependabot refresh, release-age policy, merge gates, and major-upgrade planning |
| `github-plan-wiki` | Skills: GitHub Plan Issues (parent + sub-issue hierarchy via `gh`), GitHub Wiki Plan (bilingual GitHub wiki publishing and Home index maintenance) |
| `relaypublisher-manifest` | Relaypublisher manifest creation, updates, and static validation for v1.1.0, including Windows Win32 script/file-system detection and multi-bundle macOS PKG/LOB detection |
| `repository-init` | Explicit repository initialization for license, security, language rules, and `AGENTS.md` guidance |

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
```

Use `repository-init` only with an explicit `$repository-init` request. It initializes missing governance files in a new or existing repository, records the resolved license and language profile in `.repository-init.json`, and leaves a completed repository unchanged on later invocations. It does not initialize Git, create remotes, create issues or work items, publish Wiki pages, commit, or push.

The Codex local marketplace is intended for development and team distribution. Public Codex listing submission is a separate release step after the plugins pass validation.

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

The validators check JSON syntax, matching plugin names and versions, skill frontmatter, source paths, relative links, plugin-root boundaries, and flattened GitHub Wiki template routes. The same checks run in GitHub Actions for pushes to `main` and pull requests.

When editing a plugin during local Codex development, refresh the local installation after changing the manifest and start a new conversation to pick up the updated skills.

## License

MIT. See [LICENSE](LICENSE) and the copy included in each plugin bundle.

The project-documentation skill includes its own [MIT license copy](.github/skills/project-documentation/LICENSE.txt). See [SECURITY.md](SECURITY.md) for vulnerability reporting guidance.

[Japanese overview](README_ja.md)
