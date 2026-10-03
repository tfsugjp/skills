# Test Strategy

## Record Metadata

- Owner: <known owner or unknown>
- Last updated: <YYYY-MM-DD>
- Documentation approval: <actual reference or pending>
- Related requirements, architecture, and ADRs: <relative links>

## Scope and Risk Priorities

<Critical journeys, functional and nonfunctional risks, in-scope features, exclusions with reasons, and external dependency boundaries.>

## Test Layers and Responsibilities

| Layer | Purpose | Existing tooling / paths | Owner | Entry / exit criteria |
|-------|---------|--------------------------|-------|-----------------------|
| Unit | <Purpose> | <Tool / path> | <Owner> | <Criteria> |
| Integration | <Purpose> | <Tool / path> | <Owner> | <Criteria> |
| E2E | <Critical journeys> | <Tool / path> | <Owner> | <Criteria> |

## Environment and Data Policy

<Isolated fixtures, roles, browsers/platforms, external services, secrets handling, cleanup, retention and redaction, and authorization boundaries.>

## E2E Coverage and Traceability

| Requirement / risk | Scenario ID and link | Observable assertions | Coverage gap |
|--------------------|----------------------|-----------------------|--------------|
| <Requirement> | <Link under e2e/> | <Assertions> | <Gap or none verified> |

## Execution and Quality Gates

<Exact existing commands, working directories, CI entry points, outcome definitions, skipped-test policy, retries/flakiness handling, and evidence retention. Separate planned gates from observed runs; never treat build success as E2E success.>

## Current Evidence and Gaps

<Links to actual sanitized results; otherwise state not-run. Record blockers, unverified commands, and follow-up work without inventing test counts.>

## Sources

| ID | Title | Exact URL | Checked on | Relevant claim | Relevance |
|----|-------|-----------|------------|----------------|-----------|
| S1 | <Title> | <URL> | <Date or unverified> | <Claim> | <Rationale> |

## Change History

| Date | Previous strategy / decision summary | New summary | Reason | Source IDs | Approval reference |
|------|--------------------------------------|-------------|--------|------------|--------------------|
| <Date> | <Previous or initial proposal> | <New> | <Reason> | <IDs> | <Reference or pending> |
