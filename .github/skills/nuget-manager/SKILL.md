---
name: nuget-manager
description: 'Manage NuGet packages in .NET projects/solutions. Use this skill when adding, removing, or updating NuGet package versions. It enforces using `dotnet` CLI for package management and provides strict procedures for direct file edits only when updating versions. Includes automated validation for vulnerabilities, deprecation status, and package freshness.'
---

# NuGet Manager

## Overview

This skill ensures consistent and safe management of NuGet packages across .NET projects. It prioritizes using the `dotnet` CLI to maintain project integrity, enforces a strict verification and restoration workflow for version updates, and provides automated package validation tools to check for vulnerabilities, deprecation, and freshness.

## Prerequisites

- .NET SDK installed (typically .NET 8.0 SDK or later, or a version compatible with the target solution).
- `dotnet` CLI available on your `PATH`.
- `jq` (JSON processor) OR PowerShell (for version verification using `dotnet package search`).
- **For validation workflows**: NuGetValidator tool (included in `.github/skills/nuget-manager/tools/NuGetValidator/`)

## Core Rules

1.  **NEVER** directly edit `.csproj`, `.props`, or `Directory.Packages.props` files to **add** or **remove** packages. Always use `dotnet add package` and `dotnet remove package` commands.
2.  **DIRECT EDITING** is ONLY permitted for **changing versions** of existing packages.
3.  **VERSION UPDATES** must follow the mandatory workflow:
    - Verify the target version exists on NuGet.
    - Determine if versions are managed per-project (`.csproj`) or centrally (`Directory.Packages.props`).
    - Update the version string in the appropriate file.
    - Immediately run `dotnet restore` to verify compatibility.
4.  **PACKAGE VALIDATION** should be performed before adding or updating packages:
    - Check for known vulnerabilities
    - Verify package is not deprecated
    - Alert if package hasn't been updated in > 1 year

## Workflows

### Adding a Package
Use `dotnet add [<PROJECT>] package <PACKAGE_NAME> [--version <VERSION>]`.
Example: `dotnet add src/MyProject/MyProject.csproj package Newtonsoft.Json`

**Before adding**, validate the package using the NuGetValidator tool (see **Validating Package Safety** section).

### Removing a Package
Use `dotnet remove [<PROJECT>] package <PACKAGE_NAME>`.
Example: `dotnet remove src/MyProject/MyProject.csproj package Newtonsoft.Json`

### Updating Package Versions
When updating a version, follow these steps:

1.  **Verify Version Existence**:
    Check if the version exists using the `dotnet package search` command with exact match and JSON formatting. 
    Using `jq`:
    `dotnet package search <PACKAGE_NAME> --exact-match --format json | jq -e '.searchResult[].packages[] | select(.version == "<VERSION>")'`
    Using PowerShell:
    `(dotnet package search <PACKAGE_NAME> --exact-match --format json | ConvertFrom-Json).searchResult.packages | Where-Object { $_.version -eq "<VERSION>" }`
    
2.  **Validate Package Safety** (see section below):
    Before updating, ensure the new version has no vulnerabilities and is not deprecated.

3.  **Determine Version Management**:
    - Search for `Directory.Packages.props` in the solution root. If present, versions should be managed there via `<PackageVersion Include="Package.Name" Version="1.2.3" />`.
    - If absent, check individual `.csproj` files for `<PackageReference Include="Package.Name" Version="1.2.3" />`.

4.  **Apply Changes**:
    Modify the identified file with the new version string.

5.  **Verify Stability**:
    Run `dotnet restore` on the project or solution. If errors occur, revert the change and investigate.

### Validating Package Safety

Use the NuGetValidator tool to check packages for vulnerabilities, deprecation status, and freshness:

#### 1. Validate a Specific Package Version

```bash
cd .github/skills/nuget-manager/tools/NuGetValidator
dotnet run -- validate <package-id> <version>
```

**Example**:
```bash
dotnet run -- validate Newtonsoft.Json 13.0.3
```

**Output**:
- ✓ Package is valid and safe to use
- [ERROR] Package has X vulnerability/vulnerabilities
- [ERROR] Package is deprecated
- [WARNING] Package was last published X days ago (over 1 year). Consider using a more actively maintained package.

#### 2. Find the Latest Safe Version

To find the latest version with no vulnerabilities and not deprecated:

```bash
dotnet run -- latest <package-id>
```

**Example**:
```bash
dotnet run -- latest Newtonsoft.Json
```

#### 3. List All Versions

To see all available versions of a package:

```bash
dotnet run -- versions <package-id>
```

#### 4. Output as JSON

For programmatic use, request JSON output:

```bash
dotnet run -- validate <package-id> <version> --json
```

### Workflow: Adding a New Package with Validation

1. **Find the latest safe version**:
   ```bash
   dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- latest Serilog
   ```
   
2. **Validate the version**:
   ```bash
   dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- validate Serilog 3.1.0
   ```

3. **If validation passes**, add the package:
   ```bash
   dotnet add src/MyProject/MyProject.csproj package Serilog --version 3.1.0
   ```

4. **If validation fails** (vulnerabilities, deprecated, or >1 year old), alert the user and request confirmation before proceeding.

## Package Freshness Rules

- **Stale Package**: A package is considered stale if it hasn't been updated in more than **1 year (365 days)**.
- **Warning**: When adding/updating a stale package, user confirmation is required.
- **Recommendation**: Prefer actively maintained packages whenever possible.

## Deprecation Handling

- **Deprecated Packages**: Should not be added to new projects.
- **Deprecated Versions**: If a version is deprecated, check for an alternate package recommendation in the deprecation message.
- **Migration Path**: When a deprecated package is encountered, suggest its alternate if available.

## Vulnerability Policy

- **Zero Vulnerabilities**: Do not add or update to a version with known vulnerabilities.
- **If Vulnerabilities Exist**: Alert the user immediately and recommend a patched version.
- **No Safe Version**: If no vulnerability-free version exists, escalate to user with recommendation to avoid the package entirely.

## Examples

### User: "Add Serilog to the WebApi project"
**Action**: 
1. Execute `dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- latest Serilog` to find latest safe version
2. Validate: `dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- validate Serilog <version>`
3. If valid, execute `dotnet add src/WebApi/WebApi.csproj package Serilog`

### User: "Update Newtonsoft.Json to 13.0.3 in the whole solution"
**Action**:
1. Validate 13.0.3: `dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- validate Newtonsoft.Json 13.0.3`
2. If validation fails (vulnerabilities/deprecated/stale), alert user
3. If valid, find where it's defined (e.g., `Directory.Packages.props`)
4. Edit the file to update the version
5. Run `dotnet restore`

### User: "Find the latest safe version of NLog"
**Action**: 
1. Execute `dotnet run -p .github/skills/nuget-manager/tools/NuGetValidator -- latest NLog`
2. Output the recommended version to user

## Building the NuGetValidator Tool

To build the validator tool for distribution:

```bash
cd .github/skills/nuget-manager/tools/NuGetValidator
dotnet build --configuration Release
```

Output will be in `bin/Release/net8.0/`

