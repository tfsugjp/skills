---
name: azure-devops-security-triage
description: 'End-to-end remediation workflow for GitHub Advanced Security alerts in Azure DevOps: triage open alerts, create tracking work items, drive a fix through branch and pull request, verify the re-scan closes the alert, and dismiss false positives with documented reasons. Use when the user asks to triage, remediate, or burn down Advanced Security findings.'
compatibility: 'Azure DevOps Services with GitHub Advanced Security enabled. Builds on the azure-devops-advanced-security, azure-devops-boards, azure-devops-repos, and azure-devops-pipelines skills.'
---

# Security Alert Triage Workflow (GHAzDO)

A repeatable workflow that takes GitHub Advanced Security alerts from "open" to "fixed or formally dismissed", with full work item traceability. This skill orchestrates four others — read them for API details:

- [azure-devops-advanced-security](../azure-devops-advanced-security/SKILL.md) — alert APIs (REST only)
- [azure-devops-boards](../azure-devops-boards/SKILL.md) — tracking work items
- [azure-devops-repos](../azure-devops-repos/SKILL.md) — fix branch and PR
- [azure-devops-pipelines](../azure-devops-pipelines/SKILL.md) — re-scan verification

## When to use

- "Triage the security alerts in repo X"
- "Create work items for our critical GHAS findings"
- "Drive this CodeQL alert to resolution"
- Periodic security debt burn-down for a repository

## The workflow

### 1. Inventory and prioritize

1. List active alerts on the default branch, severity-filtered first:
   `GET .../alerts?criteria.states=active&criteria.severities=critical,high&api-version=7.2-preview.1`
2. Order of attention:
   1. **Active secrets** (secret scanning with `validityResult` = active) — exposed *and* working credentials
   2. **Critical/high code scanning** alerts on the default branch
   3. **Dependency alerts** with known exploited CVEs, then by severity
3. Present the prioritized table (alert ID, type, rule/CVE, severity, location) to the user before creating anything.

### 2. Classify each alert

For each alert decide with the user: **fix**, **false positive**, or **accepted risk**. Read the alert detail (`GET .../alerts/{alertId}`) — location, rule description, and recommendation — before classifying. Anything not clearly a false positive defaults to **fix**.

### 3. Create tracking work items (fix-classified alerts)

One work item per actionable alert (or one per dependency-upgrade batch):

- Type: Bug (or the team's security work item type); tag `ghazdo`; severity mapped from the alert
- Title: `[GHAS] {ruleId or CVE}: {short description} in {file}`
- Description: alert summary, link `https://dev.azure.com/{org}/{project}/_git/{repo}/alerts/{alertId}`, recommendation text
- Add a Hyperlink relation to the alert URL
- For active secrets: the work item is "rotate + revoke + purge", not just "remove from code"

### 4. Fix via branch and PR

1. Create a fix branch (`repo_create_branch`), implement the remediation.
2. Create a PR whose description references the work item (`AB#{id}`) and the alert URL.
3. The Advanced Security PR annotation will flag remaining findings on changed lines — resolve them before completing.
4. Complete the PR per the team's policy (reviewers, build validation).

### 5. Verify closure

1. Ensure the scanning pipeline ran on the default branch after merge ([azure-devops-pipelines](../azure-devops-pipelines/SKILL.md): run/monitor the pipeline containing the CodeQL/dependency tasks).
2. Re-read the alert — state should become `fixed` automatically. **Never manually dismiss an alert to make it disappear after a fix**; if it doesn't auto-close, the fix is incomplete or the scan didn't run.
3. Comment on the work item (PR link, build link, alert now fixed) and close it.

### 6. Dismiss the rest (only with explicit user sign-off)

For confirmed false positives / accepted risks:

```text
PATCH .../alerts/{alertId}?api-version=7.2-preview.1
{"state": "dismissed", "dismissedReason": "falsePositive" | "acceptedRisk",
 "dismissedComment": "<who decided, why, and any revisit date>"}
```

Record the same rationale on the tracking work item (if one exists) and close it as "won't fix". Dismissal needs the "Advanced Security: manage and dismiss alerts" permission.

## Reporting

End each triage session with a summary the user can paste into a wiki or stand-up ([azure-devops-wiki](../azure-devops-wiki/SKILL.md) can publish it): counts by state transition (fixed / in progress / dismissed-FP / dismissed-risk / remaining), and the work item IDs created.

## Guardrails

- Classification (step 2) and every dismissal (step 6) require explicit user confirmation — these are security decisions, not editorial ones.
- Secrets: dismissing or even fixing the code does not un-leak a credential. Rotation is mandatory advice for every secret alert, including dismissed ones.
- Don't flood the backlog: batch low-severity dependency upgrades into one work item per component, and get the user's threshold (e.g. "critical/high only") before mass-creating items.
- Keep alert details out of public-facing artifacts (public wikis, public work items) — vulnerability locations are a roadmap for attackers until fixed.

## Learn more

- `microsoft_docs_search("GitHub Advanced Security Azure DevOps code scanning alerts")`
- `microsoft_docs_search("Advanced Security secret scanning push protection")`
- `microsoft_docs_search("Advanced Security risk assessment dismiss alerts")`
