---
name: azure-resource-health-diagnose
description: 'Analyze Azure resource health, diagnose issues from logs and telemetry, and create a remediation plan for identified problems.'
---

# Azure Resource Health & Issue Diagnosis

This workflow analyzes a specific Azure resource to assess its health status, diagnose potential issues using logs and telemetry data, and develop a comprehensive remediation plan for any problems discovered.

## Prerequisites
- Azure MCP server configured and authenticated
- Target Azure resource identified (name and optionally resource group/subscription)
- Prefer Azure MCP tools (`azmcp-*`) over direct Azure CLI when available

## Workflow Steps

### Step 1: Get Azure Best Practices
Execute Azure best practices tool to get diagnostic guidelines, focusing on health monitoring, log analysis, and issue resolution patterns.

### Step 2: Resource Discovery & Identification

**Resource Lookup**:
- If only resource name provided: Search across subscriptions using `azmcp-subscription-list`
- Use `az resource list --name <resource-name>` to find matching resources

**Resource Type Detection**:
- **Web Apps/Function Apps**: Application logs, performance metrics, dependency tracking
- **Virtual Machines**: System logs, performance counters, boot diagnostics
- **Cosmos DB**: Request metrics, throttling, partition statistics
- **Storage Accounts**: Access logs, performance metrics, availability
- **SQL Database**: Query performance, connection logs, resource utilization

### Step 3: Health Status Assessment
- Check resource provisioning state and operational status
- Verify service availability and responsiveness
- Review recent deployment or configuration changes

### Step 4: Log & Telemetry Analysis

Execute diagnostic queries using `azmcp-monitor-log-query`:

```kql
// Recent errors and exceptions
union isfuzzy=true AzureDiagnostics, AppServiceHTTPLogs, AppServiceAppLogs, AzureActivity
| where TimeGenerated > ago(24h)
| where Level == "Error" or ResultType != "Success"
| summarize ErrorCount=count() by Resource, ResultType, bin(TimeGenerated, 1h)
| order by TimeGenerated desc
```

### Step 5: Issue Classification & Root Cause Analysis

- **Critical**: Service unavailable, data loss, security breaches
- **High**: Performance degradation, intermittent failures, high error rates
- **Medium**: Warnings, suboptimal configuration
- **Low**: Informational alerts, optimization opportunities

### Step 6: Generate Remediation Plan
- Immediate Actions (Critical issues)
- Short-term Fixes (High/Medium issues)
- Long-term Improvements

### Step 7: Report Generation

Generate a detailed report including:
- Executive Summary
- Health Metrics (Availability, Performance, Error Rate)
- Issues Identified with Root Cause Analysis
- Prioritized Remediation Plan with Azure CLI commands
- Validation Steps
- Prevention Measures

## Error Handling
- **No Logs Available**: Suggest enabling diagnostic settings
- **Authentication Issues**: Guide user through Azure authentication setup
- **Insufficient Permissions**: List required RBAC roles

## Success Criteria
- Resource health status accurately assessed
- All significant issues identified and categorized
- Root cause analysis completed for major problems
- Actionable remediation plan with specific steps provided
