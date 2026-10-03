# Infrastructure Runbook: <Topic>

## Record Metadata

- Owner: <known owner or unknown>
- Last updated: <YYYY-MM-DD>
- Status: <proposed | accepted | retired>
- Documentation approval: <actual reference or pending>
- Related architecture and ADRs: <relative links>

## Scope and Inventory

<Environments, resources, IaC paths and revisions, dependencies, and ownership. Redact private identifiers where necessary. Label discovered configuration versus intended configuration.>

## Prerequisites and Permissions

<Supported tools and versions, least-privilege access, network constraints, configuration-variable names, and secret retrieval mechanisms. Never store secret values.>

## Preview and Deployment Procedure

<Exact repository-specific commands, working directory, safe preview/validation, deployment order, expected observations, and separate execution authorization requirements. Mark unexecuted commands unverified. Documentation approval does not authorize deployment.>

## Operations and Verification

<Health checks, telemetry, alert response, backups, recovery objectives, dependency checks, and evidence of the last verified procedure. Do not invent successful recovery.>

## Rollback and Cleanup

<Rollback conditions, known-good revision, recovery commands, irreversible effects, data-retention safeguards, and separate approval for destructive actions.>

## Sources and Selection Evidence

| ID | Title | Exact URL | Checked on | Relevant claim / section | Why it matters |
|----|-------|-----------|------------|--------------------------|----------------|
| S1 | <Title> | <URL> | <Date or unverified> | <Claim> | <Rationale> |

## Change History

| Date | Previous configuration / decision summary | New summary | Reason | Source IDs | Approval reference |
|------|-------------------------------------------|-------------|--------|------------|--------------------|
| <Date> | <Previous or initial proposal> | <New> | <Reason> | <IDs> | <Reference or pending> |
