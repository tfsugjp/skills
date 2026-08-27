# TFSUG.JP Agent Skills

Personal plugins for Azure DevOps, GitHub, .NET package maintenance, and Relaypublisher workflows (skills + agents). The repository is structured so the same plugin content can be tested with Claude Code, GitHub Copilot, and Codex.

## Plugins

| Plugin | Included skills and agents |
|---|---|
| `azure-devops-toolkit` | Skills: Azure DevOps Foundation, Boards, Repos, Pipelines, Artifacts, Test Plans, Wikis, Advanced Security, CLI, security triage. Boards uses native PowerShell on Windows and Feature-equivalent Work Items require Wiki traceability. Agents: Azure DevOps Agent, Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet vulnerability, deprecation, listing, freshness, and project-audit validation |
| `dependabot-safe-merge` | Safe Dependabot refresh, release-age policy, merge gates, and major-upgrade planning |
| `github-plan-wiki` | Skills: GitHub Plan Issues (parent + sub-issue hierarchy via `gh`), GitHub Wiki Plan (bilingual GitHub wiki publishing and Home index maintenance) |
| `relaypublisher-manifest` | Relaypublisher manifest creation, updates, and static validation, including Windows Win32 and multi-bundle macOS PKG/LOB primary detection |

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
```

The Codex local marketplace is intended for development and team distribution. Public Codex listing submission is a separate release step after the plugins pass validation.

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
