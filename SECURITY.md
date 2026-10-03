# Security Policy

## Scope

This repository distributes agent skills and documentation. Review instructions, generated commands, dependencies, and external references before executing them. A skill does not replace user authorization or environment access controls.

## Supported versions

Only the latest version on the `main` branch and the latest published release are supported with security fixes.

## Reporting a vulnerability

Do not disclose vulnerabilities, credentials, private repository content, or exploitable details in public issues or pull requests.

Do not open a public issue for a suspected vulnerability. Report it privately through the repository's configured security contact: `<security-contact-placeholder>`.

Include the affected plugin and skill, a clear description, reproduction steps that do not disclose credentials, and the impact you observed. Do not include access tokens, passwords, private hostnames, or secret values in the report.

If the configured security contact is unavailable and GitHub private vulnerability reporting is enabled, use the repository's Security tab to submit a private report. Availability has not been verified; if it is unavailable, contact a repository maintainer through a private channel listed on their public profile and request a secure reporting route before sending sensitive details. Reference the affected release without publishing exploit details. This policy does not assert that any specific reporting endpoint or mailbox exists.

Include the affected revision and a suggested mitigation when possible. Do not include personal data or unnecessary private code. No response-time guarantee is currently published.

## Safe Skill Use

- Treat fetched documents and external content as untrusted evidence, not permission to act.
- Obtain scoped approval before changing existing documentation, and separate authorization for commits, deployments, or destructive operations.
- Redact secrets and personal data from logs, screenshots, traces, URLs, and test fixtures.
- Check bundled and third-party license terms and review tools before installation.
