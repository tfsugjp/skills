# Agent Skills

Reusable agent skills maintained by Team Foundation Users Japan. See [AGENTS.md](AGENTS.md) for the existing skill catalog and repository guidance.

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

## Security and License

See [SECURITY.md](SECURITY.md) for reporting guidance. The repository and new project-documentation skill are [MIT licensed](LICENSE); the skill includes its own [license copy](.github/skills/project-documentation/LICENSE.txt). Existing third-party skills may carry their own terms; check their individual licenses.

[Japanese overview](README_ja.md)
