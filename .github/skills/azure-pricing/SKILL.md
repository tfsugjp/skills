---
name: azure-pricing
description: 'Fetches real-time Azure retail pricing using the Azure Retail Prices API (prices.azure.com) and estimates Copilot Studio agent credit consumption. Use when the user asks about the cost of any Azure service, wants to compare SKU prices, needs pricing data for a cost estimate, mentions Azure pricing, Azure costs, Azure billing, or asks about Copilot Studio pricing, Copilot Credits, or agent usage estimation. Covers compute, storage, networking, databases, AI, Copilot Studio, and all other Azure service families.'
compatibility: Requires internet access to prices.azure.com and learn.microsoft.com. No authentication needed.
metadata:
  author: anthonychu
  version: "1.2"
---

# Azure Pricing Skill

Use this skill to retrieve real-time Azure retail pricing data from the public Azure Retail Prices API. No authentication is required.

## When to Use This Skill

- User asks about the cost of an Azure service (e.g., "How much does a D4s v5 VM cost?")
- User wants to compare pricing across regions or SKUs
- User needs a cost estimate for a workload or architecture
- User mentions Azure pricing, Azure costs, or Azure billing
- User asks about reserved instance vs. pay-as-you-go pricing

## API Endpoint

```
GET https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview
```

Append `$filter` as a query parameter using OData filter syntax. Always use `api-version=2023-01-01-preview` to ensure savings plan data is included.

## Step-by-step Instructions

1. **Identify filter fields** from the user's request (service name, region, SKU, price type).
2. **Resolve the region**: the API requires `armRegionName` values in lowercase with no spaces (e.g. "East US" → `eastus`).
3. **Build the filter string** using the fields below and fetch the URL.
4. **Parse the `Items` array** from the JSON response.
5. **Follow pagination** via `NextPageLink` if needed.
6. **Calculate cost estimates** using monthly/annual formulas.
7. **Present results** in a clear summary table.

## Filterable Fields

| Field | Type | Example |
|---|---|---|
| `serviceName` | string (exact, case-sensitive) | `'Functions'`, `'Virtual Machines'`, `'Storage'` |
| `serviceFamily` | string (exact, case-sensitive) | `'Compute'`, `'Storage'`, `'Databases'` |
| `armRegionName` | string (exact, lowercase) | `'eastus'`, `'westeurope'` |
| `armSkuName` | string (exact) | `'Standard_D4s_v5'` |
| `priceType` | string | `'Consumption'`, `'Reservation'` |

## Example Filter Strings

```
# All consumption prices for Functions in East US
serviceName eq 'Functions' and armRegionName eq 'eastus' and priceType eq 'Consumption'

# D4s v5 VMs in West Europe
armSkuName eq 'Standard_D4s_v5' and armRegionName eq 'westeurope' and priceType eq 'Consumption'

# Azure AI / OpenAI pricing (Foundry Models)
serviceName eq 'Foundry Models' and armRegionName eq 'eastus' and priceType eq 'Consumption'
```

## Tips

- `serviceName` values are case-sensitive. When unsure, filter by `serviceFamily` first.
- If results are empty, try broadening the filter.
- Prices are always in USD unless `currencyCode` is specified.
- For savings plan prices, look for the `savingsPlan` array on each item.

## Copilot Studio Agent Usage Estimation

Use this section when the user asks about Copilot Studio pricing, Copilot Credits, or agent usage costs.

Key facts:
- **1 Copilot Credit = $0.01 USD**
- Credits are pooled across the entire tenant
- Fetch live billing rates from: https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management
