namespace NuGetValidator.Models;

using System.Text.Json.Serialization;

/// <summary>
/// Response from NuGet.org service index API.
/// </summary>
public class ServiceIndexResponse
{
    [JsonPropertyName("version")]
    public string? Version { get; set; }

    [JsonPropertyName("resources")]
    public List<ServiceResource>? Resources { get; set; }
}

/// <summary>
/// A service resource in the NuGet service index.
/// </summary>
public class ServiceResource
{
    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("@type")]
    public object? Types { get; set; } // Can be string or array

    [JsonPropertyName("comment")]
    public string? Comment { get; set; }
}

/// <summary>
/// Registration index response for a package.
/// </summary>
public class RegistrationIndexResponse
{
    [JsonPropertyName("@context")]
    public object? Context { get; set; }

    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("@type")]
    public object? Types { get; set; } // Can be string or array

    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("items")]
    public List<RegistrationPage>? Items { get; set; }
}

/// <summary>
/// A page in the registration index.
/// </summary>
public class RegistrationPage
{
    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("@type")]
    public object? Types { get; set; } // Can be string or array

    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("items")]
    public List<RegistrationLeaf>? Items { get; set; }

    [JsonPropertyName("lower")]
    public string? Lower { get; set; }

    [JsonPropertyName("upper")]
    public string? Upper { get; set; }
}

/// <summary>
/// A leaf in the registration page (single package version metadata).
/// </summary>
public class RegistrationLeaf
{
    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("@type")]
    public object? Types { get; set; } // Can be string or array

    [JsonPropertyName("catalogEntry")]
    public CatalogEntry? CatalogEntry { get; set; }

    [JsonPropertyName("packageContent")]
    public string? PackageContent { get; set; }
}

/// <summary>
/// Catalog entry metadata for a package version.
/// </summary>
public class CatalogEntry
{
    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("@type")]
    public object? Types { get; set; } // Can be string or array

    [JsonPropertyName("authors")]
    public string? Authors { get; set; }

    [JsonPropertyName("created")]
    public DateTime? Created { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("iconUrl")]
    public string? IconUrl { get; set; }

    [JsonPropertyName("id")]
    public string? PackageId { get; set; }

    [JsonPropertyName("isPrerelease")]
    public bool IsPrerelease { get; set; }

    [JsonPropertyName("lastEdited")]
    public DateTime? LastEdited { get; set; }

    [JsonPropertyName("licenseUrl")]
    public string? LicenseUrl { get; set; }

    [JsonPropertyName("listed")]
    public bool Listed { get; set; }

    [JsonPropertyName("packageContent")]
    public string? PackageContent { get; set; }

    [JsonPropertyName("projectUrl")]
    public string? ProjectUrl { get; set; }

    [JsonPropertyName("published")]
    public DateTime? Published { get; set; }

    [JsonPropertyName("releaseNotes")]
    public string? ReleaseNotes { get; set; }

    [JsonPropertyName("requireLicenseAcceptance")]
    public bool RequireLicenseAcceptance { get; set; }

    [JsonPropertyName("summary")]
    public string? Summary { get; set; }

    [JsonPropertyName("tags")]
    public object? Tags { get; set; } // Can be string or array

    [JsonPropertyName("title")]
    public string? Title { get; set; }

    [JsonPropertyName("version")]
    public string? Version { get; set; }

    [JsonPropertyName("vulnerabilities")]
    public List<Vulnerability>? Vulnerabilities { get; set; }

    [JsonPropertyName("deprecation")]
    public DeprecationInfo? Deprecation { get; set; }
}

/// <summary>
/// Vulnerability information for a package.
/// </summary>
public class Vulnerability
{
    [JsonPropertyName("@id")]
    public string? Id { get; set; }

    [JsonPropertyName("advisoryUrl")]
    public string? AdvisoryUrl { get; set; }

    [JsonPropertyName("severity")]
    public string? Severity { get; set; }

    [JsonPropertyName("affectedRange")]
    public string? AffectedRange { get; set; }
}

/// <summary>
/// Deprecation information for a package.
/// </summary>
public class DeprecationInfo
{
    [JsonPropertyName("@context")]
    public object? Context { get; set; }

    [JsonPropertyName("reasons")]
    public List<string>? Reasons { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("alternatePackage")]
    public AlternatePackageInfo? AlternatePackage { get; set; }
}

/// <summary>
/// Information about an alternate package.
/// </summary>
public class AlternatePackageInfo
{
    [JsonPropertyName("id")]
    public string? Id { get; set; }

    [JsonPropertyName("range")]
    public string? Range { get; set; }
}
