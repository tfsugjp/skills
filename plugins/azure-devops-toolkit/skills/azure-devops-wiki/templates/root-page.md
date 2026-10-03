<!--
Template for the repository root page: /<repo>
Write headings and prose in the language the existing wiki uses.
Replace every <...> placeholder. Use "None" for a row that does not apply; do not delete rows.
The links show Azure Repos. For a GitHub repository use https://github.com/<owner>/<repo>,
https://github.com/<owner>/<repo>/blob/<branch>/<path> for files, and link each workflow file
under .github/workflows/ in the CI/CD row.
Remove this comment before publishing.
-->

# <repo>

<One paragraph: what this repository delivers and for whom.>

| Item | Details |
| --- | --- |
| Repository | [<repo>](https://dev.azure.com/<org>/<project>/_git/<repo>) |
| Default branch | <main> |
| Infrastructure | <CLI, Azure PaaS services, hosting plans, and the IaC entry point such as `infra/main.bicep`> |
| Build outputs | <Packages, binaries, static sites, or container images the build produces> |
| CI/CD | <Azure Pipelines or GitHub Actions>: [<pipeline name>](https://dev.azure.com/<org>/<project>/_git/<repo>?path=/<azure-pipelines.yml>) |
| Design documents | [<docs/design.md>](https://dev.azure.com/<org>/<project>/_git/<repo>?path=/<docs/design.md>) |

## Child pages

| Page | Contents |
| --- | --- |
| [Plans](/<repo>/plan) | Feature, refactor, and performance plans |
| [Bugs](/<repo>/bug) | Bug fix plans |

## Overall design

<The current, final-form design of the whole repository: purpose and scope, architecture
(a Mermaid `graph` diagram is welcome), components and responsibilities, data and state,
external integrations, deployment, and constraints. Update this section in the same
publish whenever a plan or bug fix changes the specification.>
