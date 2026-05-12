# NuGetValidator Tool

A C# console application for validating NuGet packages for vulnerabilities, deprecation status, and freshness.

## Features

- **Vulnerability Detection**: Check if a package version has known security vulnerabilities
- **Deprecation Checking**: Identify deprecated packages or versions
- **Freshness Validation**: Alert when packages haven't been updated in over 1 year
- **Safe Version Recommendation**: Find the latest version with no vulnerabilities
- **JSON Output**: Support for programmatic consumption

## Building

```bash
cd NuGetValidator
dotnet build --configuration Release
```

## Usage

### Validate a Specific Version

```bash
dotnet run -- validate <package-id> <version>
```

**Example**:
```bash
dotnet run -- validate Newtonsoft.Json 13.0.3
```

**Output**:
```
Validating Newtonsoft.Json 13.0.3...

Package: Newtonsoft.Json 13.0.3
Published: 2022-10-01
Days since published: 365

✓ Package is valid and safe to use.
```

### Find Latest Safe Version

```bash
dotnet run -- latest <package-id>
```

**Example**:
```bash
dotnet run -- latest Newtonsoft.Json
```

**Output**:
```
Finding latest safe version for Newtonsoft.Json...
Latest safe version: 13.0.3
```

### List All Versions

```bash
dotnet run -- versions <package-id>
```

**Example**:
```bash
dotnet run -- versions Newtonsoft.Json
```

### JSON Output

For programmatic use:

```bash
dotnet run -- validate <package-id> <version> --json
```

**Output**:
```json
{
  "package": {
    "packageId": "Newtonsoft.Json",
    "version": "13.0.3",
    "description": "...",
    "published": "2022-10-01T00:00:00Z",
    "isDeprecated": false,
    "vulnerabilities": []
  },
  "hasVulnerabilities": false,
  "isDeprecated": false,
  "isStale": true,
  "daysSincePublished": 365,
  "issues": [
    {
      "severity": "Warning",
      "message": "Package was last published 365 days ago (over 1 year). Consider using a more actively maintained package."
    }
  ],
  "isValid": false
}
```

## Project Structure

```
NuGetValidator/
├── Program.cs              # CLI entry point
├── NuGetValidator.csproj   # Project file
├── Models/
│   ├── PackageMetadata.cs     # Package metadata DTO
│   ├── ValidationResult.cs    # Validation result DTO
│   └── NuGetServiceIndex.cs   # NuGet API response models
└── Services/
    ├── NuGetApiClient.cs        # NuGet.org API client
    └── ValidationService.cs     # Validation orchestration
```

## API Integration

- **Service**: NuGet.org v3 API
- **Index**: https://api.nuget.org/v3/index.json
- **Resources Used**:
  - RegistrationsBaseUrl - Package metadata and version history
  - VulnerabilityInfo - Known vulnerabilities (if available)

## Validation Rules

### Stale Package
- **Definition**: Package not updated for > 365 days
- **Severity**: Warning
- **Recommendation**: Consider more actively maintained alternatives

### Deprecated Package
- **Definition**: Package marked as deprecated by maintainer
- **Severity**: Error
- **Action**: Should not be added to new projects; check for alternatives

### Vulnerable Package
- **Definition**: Version has known security vulnerabilities
- **Severity**: Error
- **Action**: Do not use; find patched version

## Error Handling

The tool provides helpful error messages:

- **Package Not Found**: Returns error when package doesn't exist on NuGet.org
- **Network Issues**: Graceful handling of API connectivity problems
- **Invalid Versions**: Detects and reports invalid version strings
- **API Errors**: Verbose error output with `--verbose` flag

## Future Enhancements

- Support for pre-release package validation
- Local package source support (not just NuGet.org)
- Batch validation for multiple packages
- Integration with dotnet CLI as a plugin
- Caching for repeated API calls
