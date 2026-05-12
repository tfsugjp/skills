namespace NuGetValidator.Services;

using NuGetValidator.Models;

/// <summary>
/// Service for validating NuGet packages.
/// </summary>
public class ValidationService
{
    private const int MaxAgeInDays = 365; // 1 year
    private readonly NuGetApiClient _apiClient;

    public ValidationService(NuGetApiClient apiClient)
    {
        _apiClient = apiClient;
    }

    /// <summary>
    /// Validates a package and returns validation results.
    /// </summary>
    public async Task<ValidationResult> ValidatePackageAsync(string packageId, string version)
    {
        var metadata = await _apiClient.GetPackageMetadataAsync(packageId, version);

        if (metadata == null)
        {
            throw new InvalidOperationException($"Package {packageId} version {version} not found");
        }

        var daysSincePublished = (int)(DateTime.UtcNow - metadata.Published).TotalDays;
        var isStale = daysSincePublished > MaxAgeInDays;

        var issues = new List<ValidationIssue>();

        // Check for vulnerabilities
        if (metadata.Vulnerabilities.Count > 0)
        {
            issues.Add(new ValidationIssue
            {
                Severity = IssueSeverity.Error,
                Message = $"Package has {metadata.Vulnerabilities.Count} known vulnerability/vulnerabilities: {string.Join("; ", metadata.Vulnerabilities)}"
            });
        }

        // Check for deprecation
        if (metadata.IsDeprecated)
        {
            issues.Add(new ValidationIssue
            {
                Severity = IssueSeverity.Error,
                Message = $"Package is deprecated: {metadata.DeprecationMessage ?? "No reason provided"}"
            });
        }

        // Check for stale package (not updated in 1+ year)
        if (isStale)
        {
            issues.Add(new ValidationIssue
            {
                Severity = IssueSeverity.Warning,
                Message = $"Package was last published {daysSincePublished} days ago (over 1 year). Consider using a more actively maintained package."
            });
        }

        return new ValidationResult
        {
            Package = metadata,
            IsStale = isStale,
            DaysSincePublished = daysSincePublished,
            Issues = issues
        };
    }

    /// <summary>
    /// Finds the latest non-deprecated, non-vulnerable version of a package.
    /// </summary>
    public async Task<string?> FindLatestSafeVersionAsync(string packageId)
    {
        var versions = await _apiClient.GetPackageVersionsAsync(packageId);

        if (!versions.Any())
        {
            return null;
        }

        // Sort versions in descending order (latest first)
        var sortedVersions = versions
            .OrderByDescending(v => ParseVersion(v))
            .ToList();

        foreach (var version in sortedVersions)
        {
            var metadata = await _apiClient.GetPackageMetadataAsync(packageId, version);

            if (metadata != null &&
                !metadata.IsDeprecated &&
                metadata.Vulnerabilities.Count == 0)
            {
                return version;
            }
        }

        return null;
    }

    /// <summary>
    /// Parses a version string for sorting.
    /// </summary>
    private static Version ParseVersion(string versionString)
    {
        try
        {
            // Handle prerelease versions
            var basePart = versionString.Split('-')[0];
            return Version.Parse(basePart);
        }
        catch
        {
            return new Version(0, 0, 0);
        }
    }
}
