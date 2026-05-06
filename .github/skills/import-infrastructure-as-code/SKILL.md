---
name: import-infrastructure-as-code
description: 'Import existing Azure resources into Terraform using Azure CLI discovery and Azure Verified Modules (AVM). Use when asked to reverse-engineer live Azure infrastructure, generate Infrastructure as Code from existing subscriptions/resource groups/resource IDs, map dependencies, derive exact import addresses from downloaded module source, prevent configuration drift, and produce AVM-based Terraform files ready for validation and planning across any Azure resource type.'
---

# Import Infrastructure as Code (Azure -> Terraform with AVM)

Convert existing Azure infrastructure into maintainable Terraform code using discovery data and Azure Verified Modules.

## When to Use This Skill

Use this skill when the user asks to:
- Import existing Azure resources into Terraform
- Generate IaC from live Azure environments
- Recreate infrastructure from a subscription or resource group
- Map dependencies between discovered Azure resources
- Use AVM modules instead of handwritten `azurerm_*` resources

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Terraform CLI installed
- Access to the target subscription or resource group

## Step-by-Step Workflows

### 1) Authenticate and Set Context

```bash
az login
az account set --subscription <subscription-id>
az account show --query "{subscriptionId:id, name:name, tenantId:tenantId}" -o json
```

### 2) Run Discovery Commands

```bash
# Subscription scope
az resource list --subscription <subscription-id> -o json

# Resource group scope
az resource list --resource-group <resource-group-name> -o json

# Specific resource scope
az resource show --ids <resource-id> -o json
```

### 3) Resolve Dependencies

Parse exported JSON and map:
- Parent-child relationships (e.g., NIC -> Subnet -> VNet)
- Cross-resource references in `properties`
- Ordering for Terraform creation

Generate documentation:
- `exported-resources.json` with all discovered resources
- `EXPORTED-ARCHITECTURE.MD` with human-readable architecture overview

### 4) Select Azure Verified Modules (Required)

Use the latest AVM version for each resource type.

**Official AVM Index URLs:**
- Terraform Resource Modules: `https://raw.githubusercontent.com/Azure/Azure-Verified-Modules/refs/heads/main/docs/static/module-indexes/TerraformResourceModules.csv`
- Terraform Pattern Modules: `https://raw.githubusercontent.com/Azure/Azure-Verified-Modules/refs/heads/main/docs/static/module-indexes/TerraformPatternModules.csv`

### 5) Read the Module README Before Writing Code (Mandatory)

For each AVM module, fetch its README:
```
https://raw.githubusercontent.com/Azure/terraform-azurerm-avm-res-<service>-<resource>/refs/heads/main/README.md
```

From the README, extract:
1. **Required Inputs** — every input the module requires
2. **Optional Inputs** — exact Terraform variable names and types
3. **Usage examples** — patterns for resource group identifiers and child resources

### 6) Generate Terraform Files

Produce:
- `providers.tf` with `azurerm` provider and required version constraints
- `main.tf` with AVM module blocks and explicit dependencies
- `variables.tf` for environment-specific values
- `outputs.tf` for key IDs and endpoints
- `terraform.tfvars.example` with placeholder values

Pin module versions explicitly:
```hcl
module "example" {
  source  = "Azure/<module>/azurerm"
  version = "<latest-compatible-version>"
}
```

### 7) Validate Generated Code

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan
```

## Execution Rules

- Do not continue if scope is missing.
- Prefer AVM modules first; justify each non-AVM fallback explicitly.
- Read the README for every AVM module before writing code.
- Never write import addresses from memory — grep downloaded module source.
- Never treat ARM resource IDs as file paths.
- Do not declare the import complete until `terraform plan` shows 0 destroys and 0 unwanted changes.

## References

- [Azure Verified Modules index (Terraform)](https://github.com/Azure/Azure-Verified-Modules/tree/main/docs/static/module-indexes)
- [Terraform AVM Registry namespace](https://registry.terraform.io/namespaces/Azure)
