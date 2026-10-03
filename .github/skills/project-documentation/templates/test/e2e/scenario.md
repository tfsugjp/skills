# E2E: <Critical Flow>

## Record Metadata

- Scenario ID: <stable ID>
- Owner: <known owner or unknown>
- Last updated: <YYYY-MM-DD>
- Documentation approval: <actual reference or pending>
- Requirements / ADRs / strategy: <relative links>

## Scenario Definition

### Goal and Boundaries

<Critical journey, risk, component boundaries, real versus mocked dependencies, and coverage exclusions.>

### Prerequisites and Fixtures

<Environment, accounts/roles, isolated seed data, feature flags, supported browser/platform matrix, and safe cleanup. Reference secret variable names only.>

### Steps and Assertions

| Step | User action / input | Observable expected result |
|------|---------------------|----------------------------|
| 1 | <Action> | <Explicit assertion> |

### Negative Paths and Quality Checks

<Authorization failures, validation, dependency outages/recovery, and accessibility checks when relevant. State exclusions explicitly.>

### Execution and Cleanup Instructions

<Working directory, exact existing test command, tooling requirements, deterministic setup and cleanup. Mark commands unverified until executed. Obtain separate permission for destructive, production, or chargeable execution.>

## Run Evidence

This section records observations, not intentions. If no run occurred, use `not-run`, omit invented counts/artifacts, and state the limitation. Preserve earlier run rows. Adding evidence to an existing file requires scoped approval.

| Run ID | Date / time zone | Revision | Environment | Tool / browser versions | Exact command | Outcome | Passed / failed / skipped counts | Retries | Sanitized artifacts / blocker |
|--------|------------------|----------|-------------|-------------------------|---------------|---------|----------------------------------|---------|-------------------------------|
| <ID or none> | <Actual date or N/A> | <Revision or unknown> | <Environment or N/A> | <Versions or unknown> | <Executed command or not executed> | <not-run / passed / failed / blocked / flaky> | <Actual counts or N/A> | <Actual count or N/A> | <Evidence or limitation> |

Record first-attempt and retry outcomes. Do not describe skipped, flaky, or blocked scenarios as unconditional passes. Never link sensitive session traces, screenshots, or tokens without sanitization and authorized access controls.

## Sources

| ID | Title | Exact URL | Checked on | Relevant claim | Relevance |
|----|-------|-----------|------------|----------------|-----------|
| S1 | <Title> | <URL> | <Date or unverified> | <Claim> | <Rationale> |

## Change History

| Date | Previous scenario / decision summary | New summary | Reason | Source IDs | Approval reference |
|------|--------------------------------------|-------------|--------|------------|--------------------|
| <Date> | <Previous or initial proposal> | <New> | <Reason> | <IDs> | <Reference or pending> |
