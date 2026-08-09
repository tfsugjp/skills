# TFSUG.JP Agent Skills

Personal, skills-only plugins for Azure DevOps and .NET package maintenance. The repository is structured so the same plugin content can be tested with Claude Code, GitHub Copilot, and Codex.

## Plugins

| Plugin | Included skills |
|---|---|
| `azure-devops-toolkit` | Azure DevOps Foundation, Boards, Repos, Pipelines, Artifacts, Test Plans, Wikis, Advanced Security, CLI, and security triage |
| `nuget-validate` | NuGet vulnerability, deprecation, listing, freshness, and project-audit validation |

All plugins are distributed under the MIT License. The plugin bundles contain no credentials and do not configure an MCP server automatically. Azure DevOps authentication and permissions remain the responsibility of the user.

## Install from the Claude Code marketplace

Add the repository as a marketplace, then install the plugin you need:

```text
claude plugin marketplace add tfsugjp/skills
claude plugin install azure-devops-toolkit@tfsugjp-agent-skills
claude plugin install nuget-validate@tfsugjp-agent-skills
```

## Install from the GitHub Copilot marketplace

The Copilot CLI reads the shared Claude marketplace catalog in this repository:

```text
copilot plugin marketplace add tfsugjp/skills
copilot plugin install azure-devops-toolkit@tfsugjp-agent-skills
copilot plugin install nuget-validate@tfsugjp-agent-skills
```

## Install from the Codex repository-local marketplace

Set `REPO_ROOT` to the checked-out repository directory. Codex uses the repository-local catalog under `.agents/plugins/`:

```text
codex plugin marketplace add "$REPO_ROOT"
codex plugin add azure-devops-toolkit@tfsugjp-agent-skills
codex plugin add nuget-validate@tfsugjp-agent-skills
```

The Codex local marketplace is intended for development and team distribution. Public Codex listing submission is a separate release step after the plugins pass validation.

## Development validation

Run the repository validator from the repository root:

```text
python scripts/validate_marketplaces.py
```

The validator checks JSON syntax, matching plugin names and versions, skill frontmatter, source paths, relative links, and plugin-root boundaries. The same check runs in GitHub Actions for pushes to `main` and pull requests.

When editing a plugin during local Codex development, refresh the local installation after changing the manifest and start a new conversation to pick up the updated skills.

## License

MIT. See [LICENSE](LICENSE) and the copy included in each plugin bundle.
