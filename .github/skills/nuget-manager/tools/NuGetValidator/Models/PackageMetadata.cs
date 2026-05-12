namespace NuGetValidator.Models;

/// <summary>
/// Represents metadata for a NuGet package from the NuGet.org API.
/// </summary>
public class PackageMetadata
{
    /// <summary>
    /// Package ID (lowercase).
    /// </summary>
    public required string PackageId { get; init; }

    /// <summary>
    /// Package version.
    /// </summary>
    public required string Version { get; init; }

    /// <summary>
    /// Package description.
    /// </summary>
    public string? Description { get; init; }

    /// <summary>
    /// When the package was last published.
    /// </summary>
    public DateTime Published { get; init; }

    /// <summary>
    /// Indicates if the package is deprecated.
    /// </summary>
    public bool IsDeprecated { get; init; }

    /// <summary>
    /// Deprecation message if applicable.
    /// </summary>
    public string? DeprecationMessage { get; init; }

    /// <summary>
    /// Known vulnerabilities for this package version.
    /// </summary>
    public List<string> Vulnerabilities { get; init; } = new();

    /// <summary>
    /// Download count for this version.
    /// </summary>
    public long? DownloadCount { get; init; }
}
