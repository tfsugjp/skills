namespace NuGetValidator.Models;

/// <summary>
/// Result of package validation.
/// </summary>
public class ValidationResult
{
    /// <summary>
    /// The package being validated.
    /// </summary>
    public required PackageMetadata Package { get; init; }

    /// <summary>
    /// Whether the package has any vulnerabilities.
    /// </summary>
    public bool HasVulnerabilities => Package.Vulnerabilities.Count > 0;

    /// <summary>
    /// Whether the package is deprecated.
    /// </summary>
    public bool IsDeprecated => Package.IsDeprecated;

    /// <summary>
    /// Whether the package hasn't been updated in over 1 year.
    /// </summary>
    public bool IsStale { get; init; }

    /// <summary>
    /// Days since last published.
    /// </summary>
    public int DaysSincePublished { get; init; }

    /// <summary>
    /// Validation warnings/issues.
    /// </summary>
    public List<ValidationIssue> Issues { get; init; } = new();

    /// <summary>
    /// Whether the validation passed (no vulnerabilities, not deprecated, not stale).
    /// </summary>
    public bool IsValid => !HasVulnerabilities && !IsDeprecated && !IsStale;
}

/// <summary>
/// An issue found during validation.
/// </summary>
public class ValidationIssue
{
    /// <summary>
    /// Issue severity level.
    /// </summary>
    public required IssueSeverity Severity { get; init; }

    /// <summary>
    /// Issue description.
    /// </summary>
    public required string Message { get; init; }
}

/// <summary>
/// Severity levels for validation issues.
/// </summary>
public enum IssueSeverity
{
    /// <summary>
    /// Informational message.
    /// </summary>
    Info = 0,

    /// <summary>
    /// Warning - should review but can proceed.
    /// </summary>
    Warning = 1,

    /// <summary>
    /// Error - should not proceed.
    /// </summary>
    Error = 2
}
