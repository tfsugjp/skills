# Major and incompatible upgrade review

Use this workflow for a numeric major increase, a pre-1.0 minor boundary, or an ecosystem-specific compatibility boundary.

## Pull request handling

1. Refresh the same Dependabot pull request to the newest 24-hour eligible stable release.
2. Convert the entire grouped pull request to Draft before planning.
3. If draft conversion is unavailable, apply an existing breaking-change label and add a blocking comment. Do not invent a label and do not enable auto-merge.
4. Capture the refreshed head SHA and review the final diff. Any later head change invalidates the review.

## Official evidence

Prefer evidence in this order:

1. Official migration or upgrade guide.
2. Official release notes for every crossed version range.
3. Maintainer changelog.
4. Official API and configuration documentation.

Record document titles, release ranges, and relevant headings. Follow the target repository rule when external addresses are prohibited; do not place an address in the issue. Missing, conflicting, or incomplete evidence is an unresolved risk and blocks implementation approval.

Check at least:

- Removed, renamed, or behavior-changing APIs.
- Configuration schema and default changes.
- Runtime, compiler, package-manager, operating-system, and toolchain requirements.
- Data, wire-format, persistence, and authentication changes.
- Deprecations that become errors.
- Transitive dependency or plugin compatibility constraints.
- Required migration order and rollback limitations.

## Source review

Map every documented change to repository evidence:

- Search imports, API calls, configuration keys, command-line arguments, serialization contracts, extensions, build files, and deployment files.
- Review the pull request diff and all dependency-related generated files.
- Build and test with the target runtime and toolchain.
- Add focused tests for each affected behavior and retain failing evidence when the migration is incomplete.
- Identify rollout checkpoints and a version-control rollback point.
- Treat unexplained build success as insufficient when the official material describes a behavior change.

## Implementation-plan issue

Create or update one issue per dependency and target major. Search the exact marker before creating anything:

`<!-- dependabot-safe-merge:key=<ecosystem>:<package>:<target-major> -->`

Generate the body with `scripts/major_plan.py`. It must contain:

- Current and target versions.
- Official documentation reviewed.
- Incompatible and breaking changes.
- Affected code.
- A phased implementation plan.
- Tests and rollback.
- Acceptance criteria.
- Unresolved questions.

Relate the pull request as `#number`. If the marker already exists, update that issue instead of creating another. Apply the repository's existing enhancement or dependency label only when its meaning matches.

## Completion rule

Keep the pull request unmerged. Report the draft state, selected target, reviewed evidence, affected code, build and test results, implementation-plan issue number, and unresolved risks.
