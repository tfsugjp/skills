# Setup: <Topic>

## Record Metadata

- Owner: <known owner or unknown>
- Last updated: <YYYY-MM-DD>
- Documentation approval: <actual reference or pending>
- Related architecture / infrastructure / ADRs: <relative links>

## Supported Environment

<OS, runtime and tool versions, prerequisites, least-privilege access, and known restrictions. Verify version-specific claims against current official sources.>

## Configuration

| Variable / setting | Purpose | Required | Safe example / retrieval mechanism |
|--------------------|---------|----------|-------------------------------------|
| <Name> | <Purpose> | <Yes/no> | <Non-secret example; no credentials> |

## Installation and Startup

<Numbered steps with exact repository-specific working directories and commands, expected observations, and any approval-required installations/network access. Distinguish verified commands from unverified instructions.>

## Smoke Verification

<Minimal health check and expected result. Record actual environment, revision, date, and outcome if executed; otherwise not-run. A smoke check does not establish E2E success.>

## Troubleshooting

| Symptom | Evidence to collect | Likely cause | Safe resolution / source |
|---------|---------------------|--------------|--------------------------|
| <Symptom> | <Sanitized evidence> | <Verified cause or hypothesis> | <Steps / URL> |

## Cleanup and Next Steps

<Safe shutdown, cleanup risks requiring separate approval, and links to E2E and operational guides.>

## Sources and Version Evidence

| ID | Title | Exact URL | Checked on | Relevant claim / section | Why it matters |
|----|-------|-----------|------------|--------------------------|----------------|
| S1 | <Title> | <URL> | <Date or unverified> | <Claim> | <Rationale> |

## Change History

| Date | Previous setup / decision summary | New summary | Reason | Source IDs | Approval reference |
|------|-----------------------------------|-------------|--------|------------|--------------------|
| <Date> | <Previous or initial proposal> | <New> | <Reason> | <IDs> | <Reference or pending> |
