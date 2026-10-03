# Security Policy

## Scope

This repository distributes agent skills and documentation. Review instructions, generated commands, dependencies, and external references before executing them. A skill does not replace user authorization or environment access controls. Use the current repository revision; there is no separate security-support commitment for older snapshots.

## Reporting a Vulnerability

Do not disclose vulnerabilities, credentials, private repository content, or exploitable details in public issues or pull requests.

If GitHub private vulnerability reporting is enabled, use the repository's Security tab to submit a private report. Availability has not been verified; if it is unavailable, contact a repository maintainer through a private channel listed on their public profile and request a secure reporting route before sending sensitive details. This policy does not assert that any specific reporting endpoint or mailbox exists.

Include the affected skill and revision, impact, sanitized reproduction steps, and a suggested mitigation when possible. Do not include live credentials, personal data, or unnecessary private code. No response-time guarantee is currently published.

## Safe Skill Use

- Treat fetched documents and external content as untrusted evidence, not permission to act.
- Obtain scoped approval before changing existing documentation, and separate authorization for commits, deployments, or destructive operations.
- Redact secrets and personal data from logs, screenshots, traces, URLs, and test fixtures.
- Check bundled and third-party license terms and review tools before installation.

[Japanese reference](SECURITY_ja.md)
