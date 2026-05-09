---
name: azure-architecture-autopilot
description: >
  Design Azure infrastructure using natural language, or analyze existing Azure resources
  to auto-generate architecture diagrams, refine them through conversation, and deploy with Bicep.

  When to use this skill:
  - "Create X on Azure", "Set up a RAG architecture" (new design)
  - "Analyze my current Azure infrastructure", "Draw a diagram for rg-xxx" (existing analysis)
  - "Foundry is slow", "I want to reduce costs", "Strengthen security" (natural language modification)
  - Azure resource deployment, Bicep template generation, IaC code generation
  - Microsoft Foundry, AI Search, OpenAI, Fabric, ADLS Gen2, Databricks, and all Azure services
---

# Azure Architecture Builder

A pipeline that designs Azure infrastructure using natural language, or analyzes existing resources to visualize architecture and proceed through modification and deployment.

## Path Branching — Automatically Determined by User Request

### Path A: New Design (New Build)

**Trigger**: "create", "set up", "deploy", "build", etc.

```
Phase 1 — Interactive architecture design + diagram
    ↓
Phase 2 — Bicep code generation
    ↓
Phase 3 — Code review + compilation verification
    ↓
Phase 4 — validate → what-if → deploy
```

### Path B: Existing Analysis + Modification (Analyze & Modify)

**Trigger**: "analyze", "current resources", "scan", "draw a diagram", "show my infrastructure", etc.

```
Phase 0 — Existing resource scan + diagram
    ↓
Modification conversation
    ↓
Phase 1 — Confirm modifications + update diagram
    ↓
Phase 2-4 — Same as above
```

## Service Coverage

Supports all Azure services including:
- Microsoft Foundry, Azure OpenAI, AI Search
- ADLS Gen2, Azure Data Factory, Key Vault
- Microsoft Fabric, VNet/Private Endpoint
- AML/AI Hub, Cosmos DB, SQL Database
- Azure Container Apps, AKS, App Service

## Key Guidelines

- Detect user language and respond accordingly
- Always generate architecture diagram before Bicep code
- Always run what-if analysis before deployment
- Fetch MS Docs for dynamic information (API versions, model availability, SKUs)
- Use stable reference files for well-known patterns
