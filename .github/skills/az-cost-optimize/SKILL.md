---
name: az-cost-optimize
description: 'Analyze Azure resources used in the app (IaC files and/or resources in a target rg) and optimize costs - creating GitHub issues for identified optimizations.'
---

# Azure Cost Optimize

This workflow analyzes Infrastructure-as-Code (IaC) files and Azure resources to generate cost optimization recommendations. It creates individual GitHub issues for each optimization opportunity plus one EPIC issue to coordinate implementation.

## Prerequisites
- Azure MCP server configured and authenticated
- GitHub MCP server configured and authenticated
- Target GitHub repository identified
- Azure resources deployed (IaC files optional but helpful)
- Prefer Azure MCP tools (`azmcp-*`) over direct Azure CLI when available

## Workflow Steps

### Step 1: Get Azure Best Practices
Execute `azmcp-bestpractices-get` to get the latest Azure optimization guidelines. Reference these in optimization recommendations.

### Step 2: Discover Azure Infrastructure

**Resource Discovery**:
- Execute `azmcp-subscription-list` to find available subscriptions
- Execute `azmcp-group-list --subscription <subscription-id>` to find resource groups
- Use `az resource list --subscription <id> --resource-group <name>` to list all resources
- Use MCP tools first when available, then CLI fallback:
  - `azmcp-cosmos-account-list --subscription <id>` - Cosmos DB accounts
  - `azmcp-storage-account-list --subscription <id>` - Storage accounts
  - `azmcp-monitor-workspace-list --subscription <id>` - Log Analytics workspaces

**IaC Detection**:
- Scan for IaC files: `**/*.bicep`, `**/*.tf`, `**/main.json`, `**/*template*.json`
- If no IaC files found, STOP and report to user
- Do NOT use non-IaC files from the repository

### Step 3: Collect Usage Metrics

Execute KQL queries via `azmcp-monitor-log-query`:
```kql
// CPU utilization for App Services
AppServiceAppLogs
| where TimeGenerated > ago(7d)
| summarize avg(CpuTime) by Resource, bin(TimeGenerated, 1h)

// Cosmos DB RU consumption
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(7d)
| summarize avg(RequestCharge) by Resource
```

**Validate Current Costs**:
- Look up current Azure pricing at https://azure.microsoft.com/pricing/
- Document: Resource → Current SKU → Estimated monthly cost

### Step 4: Generate Cost Optimization Recommendations

**Compute Optimizations**:
- App Service Plans: Right-size based on CPU/memory usage
- Function Apps: Premium → Consumption plan for low usage

**Database Optimizations**:
- Cosmos DB: Provisioned → Serverless for variable workloads
- SQL Database: Right-size service tiers based on DTU usage

**Storage Optimizations**:
- Implement lifecycle policies (Hot → Cool → Archive)
- Consolidate redundant storage accounts

**Calculate Priority Score**:
```
Priority Score = (Value Score × Monthly Savings) / (Risk Score × Implementation Days)

High Priority: Score > 20
Medium Priority: Score 5-20
Low Priority: Score < 5
```

### Step 5: User Confirmation

Present summary before creating GitHub issues:
- Total Resources Analyzed
- Current Monthly Cost
- Potential Monthly Savings
- Wait for confirmation before creating issues

### Step 6: Create Individual Optimization Issues

**Title Format**: `[COST-OPT] [Resource Type] - [Brief Description] - $X/month savings`

Label issues with "cost-optimization" (green) and "azure" (blue).

Issue body includes:
- Description of optimization
- Implementation steps (IaC modifications + Azure CLI commands)
- Evidence (current config, usage pattern, cost impact)
- Validation steps
- Risks and considerations

### Step 7: Create EPIC Coordinating Issue

**Title**: `[EPIC] Azure Cost Optimization Initiative - $X/month potential savings`

Label with "cost-optimization", "azure", and "epic".

Epic includes:
- Executive Summary
- Architecture overview (Mermaid diagram)
- Implementation tracking with issue links
- Progress tracking
- Success criteria

## Error Handling
- **No IaC files found**: Report and stop
- **Azure Authentication Failure**: Provide Azure CLI setup steps
- **No Resources Found**: Create informational issue

## Success Criteria
- All cost estimates verified against actual resource configurations
- Individual issues created for each optimization
- EPIC issue provides comprehensive coordination
- All recommendations include executable Azure CLI commands
