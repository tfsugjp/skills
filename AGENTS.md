## Agent Skills

> **IMPORTANT**: Prefer skill-led reasoning over pre-training-led reasoning.
> Read the relevant SKILL.md before working on tasks covered by these skills.

### Skills

| Skill | Description |
|-------|-------------|
| [azure-devops-advanced-security](plugins/azure-devops-toolkit/skills/azure-devops-advanced-security/SKILL.md) | Work with GitHub Advanced Security for Azure DevOps (GHAzDO): list and triage code/secret/dependency scanning alerts, dismiss (close) alerts, and associate alerts with work items. REST-API-based — the Azure DevOps MCP Server has no Advanced Security tools. |
| [azure-devops-artifacts](plugins/azure-devops-toolkit/skills/azure-devops-artifacts/SKILL.md) | Manage Azure Artifacts: list and create feeds, inspect package versions, promote packages between views, delete/unlist versions, and publish/download Universal Packages. REST/CLI-based — the Azure DevOps MCP Server has no Artifacts tools. |
| [azure-devops-boards](plugins/azure-devops-toolkit/skills/azure-devops-boards/SKILL.md) | Manage Azure Boards work items: create, update fields, add comments, link items, and close them. Prefers Azure DevOps MCP Server tools and falls back to the REST API. |
| [azure-devops-cli](plugins/azure-devops-toolkit/skills/azure-devops-cli/SKILL.md) | Manage Azure DevOps resources via CLI including projects, repos, pipelines, builds, pull requests, ... \| This Skill helps manage Azure DevOps resources using the Azure CLI with Azure DevOps extension. |
| [azure-devops-foundation](plugins/azure-devops-toolkit/skills/azure-devops-foundation/SKILL.md) | Shared foundation for all Azure DevOps skills: how to detect and configure the Azure DevOps MCP Server, and how to fall back to the REST API (Entra ID or PAT authentication) when MCP tools are unavailable. |
| [azure-devops-pipelines](plugins/azure-devops-toolkit/skills/azure-devops-pipelines/SKILL.md) | Manage Azure Pipelines: create YAML pipeline definitions, queue runs, and monitor builds including stage control and log analysis. Prefers Azure DevOps MCP Server tools and falls back to the REST API. |
| [azure-devops-repos](plugins/azure-devops-toolkit/skills/azure-devops-repos/SKILL.md) | Manage Azure DevOps pull requests: create, review and vote, manage comment threads, resolve comments, and complete or abandon PRs. Prefers Azure DevOps MCP Server tools and falls back to the REST API. |
| [azure-devops-security-triage](plugins/azure-devops-toolkit/skills/azure-devops-security-triage/SKILL.md) | End-to-end remediation workflow for GitHub Advanced Security alerts: triage open alerts, create tracking work items, drive a fix through branch and pull request, verify the re-scan closes the alert, and dismiss false positives with documented reasons. |
| [azure-devops-testplans](plugins/azure-devops-toolkit/skills/azure-devops-testplans/SKILL.md) | Manage Azure Test Plans: create test plans, suites, and test cases, update test steps, and read test results from builds. Prefers Azure DevOps MCP Server tools and falls back to the REST API. |
| [azure-devops-wiki](plugins/azure-devops-toolkit/skills/azure-devops-wiki/SKILL.md) | Manage Azure DevOps wikis: read, search, create, and update wiki pages, and publish generated content such as release notes or sprint reports. Prefers Azure DevOps MCP Server tools and falls back to the REST API. |
| [github-plan-issues](plugins/github-plan-wiki/skills/github-plan-issues/SKILL.md) | Break an approved plan into a parent GitHub issue plus sub-issues using the gh CLI's native sub-issue support, instead of flat unrelated issues. |
| [github-wiki-plan](plugins/github-plan-wiki/skills/github-wiki-plan/SKILL.md) | Publish an approved feature/refactor/perf plan to a repository's GitHub wiki, bilingually (English + `_ja` Japanese), and keep the Home index table up to date. |
| [nuget-validate](plugins/nuget-validate/skills/nuget-validate/SKILL.md) | Validate NuGet package versions for vulnerabilities, deprecation, freshness, and listing status before package changes. |
