namespace NuGetValidator.Services;

using System.Text.Json;
using System.Text.Json.Serialization;
using NuGetValidator.Models;

/// <summary>
/// Client for interacting with NuGet.org API.
/// </summary>
public class NuGetApiClient
{
    private const string NuGetServiceIndexUrl = "https://api.nuget.org/v3/index.json";
    private const string DefaultUserAgent = "NuGetValidator/1.0";

    private readonly HttpClient _httpClient;
    private string? _registrationBaseUrl;

    public NuGetApiClient(HttpClient? httpClient = null)
    {
        _httpClient = httpClient ?? new HttpClient();
        _httpClient.DefaultRequestHeaders.Add("User-Agent", DefaultUserAgent);
    }

    /// <summary>
    /// Gets the registration base URL from the service index.
    /// </summary>
    private async Task<string> GetRegistrationBaseUrlAsync()
    {
        if (!string.IsNullOrEmpty(_registrationBaseUrl))
        {
            return _registrationBaseUrl;
        }

        var response = await _httpClient.GetAsync(NuGetServiceIndexUrl);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        
        // Parse as dynamic to handle flexible structure
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        if (!root.TryGetProperty("resources", out var resourcesArray))
        {
            throw new InvalidOperationException("resources not found in service index");
        }

        foreach (var resource in resourcesArray.EnumerateArray())
        {
            if (!resource.TryGetProperty("@type", out var types))
            {
                continue;
            }

            // @type can be array or string
            var typesList = new List<string>();
            if (types.ValueKind == JsonValueKind.Array)
            {
                foreach (var type in types.EnumerateArray())
                {
                    if (type.GetString() is string t)
                    {
                        typesList.Add(t);
                    }
                }
            }
            else if (types.GetString() is string typeStr)
            {
                typesList.Add(typeStr);
            }

            // Check for RegistrationsBaseUrl
            if (typesList.Any(t => t.Contains("RegistrationsBaseUrl", StringComparison.OrdinalIgnoreCase)))
            {
                if (resource.TryGetProperty("@id", out var id) && id.GetString() is string idStr)
                {
                    _registrationBaseUrl = idStr;
                    return _registrationBaseUrl;
                }
            }
        }

        throw new InvalidOperationException("RegistrationsBaseUrl not found in service index");
    }

    /// <summary>
    /// Fetches metadata for a specific package and version.
    /// </summary>
    public async Task<PackageMetadata?> GetPackageMetadataAsync(string packageId, string version)
    {
        try
        {
            var baseUrl = await GetRegistrationBaseUrlAsync();
            var registrationUrl = $"{baseUrl.TrimEnd('/')}/{packageId.ToLowerInvariant()}/index.json";

            var response = await _httpClient.GetAsync(registrationUrl);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync();
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var index = JsonSerializer.Deserialize<RegistrationIndexResponse>(json, options);

            if (index?.Items == null)
            {
                return null;
            }

            // Find the version in pages
            foreach (var page in index.Items)
            {
                if (page.Items == null)
                {
                    continue;
                }

                var leaf = page.Items.FirstOrDefault(l =>
                    l.CatalogEntry?.Version?.Equals(version, StringComparison.OrdinalIgnoreCase) == true);

                if (leaf?.CatalogEntry != null)
                {
                    return MapToPackageMetadata(leaf.CatalogEntry);
                }
            }

            return null;
        }
        catch (HttpRequestException ex)
        {
            throw new InvalidOperationException($"Failed to fetch package metadata for {packageId} {version}", ex);
        }
    }

    /// <summary>
    /// Gets all versions of a package.
    /// </summary>
    public async Task<IEnumerable<string>> GetPackageVersionsAsync(string packageId)
    {
        try
        {
            var baseUrl = await GetRegistrationBaseUrlAsync();
            var registrationUrl = $"{baseUrl.TrimEnd('/')}/{packageId.ToLowerInvariant()}/index.json";

            var response = await _httpClient.GetAsync(registrationUrl);
            if (!response.IsSuccessStatusCode)
            {
                return Enumerable.Empty<string>();
            }

            var json = await response.Content.ReadAsStringAsync();
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var index = JsonSerializer.Deserialize<RegistrationIndexResponse>(json, options);

            var versions = new List<string>();

            if (index?.Items != null)
            {
                foreach (var page in index.Items)
                {
                    if (page.Items != null)
                    {
                        versions.AddRange(page.Items
                            .Where(l => l.CatalogEntry?.Version != null)
                            .Select(l => l.CatalogEntry!.Version!));
                    }
                }
            }

            return versions;
        }
        catch (HttpRequestException ex)
        {
            throw new InvalidOperationException($"Failed to fetch versions for {packageId}", ex);
        }
    }

    private static PackageMetadata MapToPackageMetadata(CatalogEntry entry)
    {
        return new PackageMetadata
        {
            PackageId = entry.PackageId ?? entry.Id ?? "unknown",
            Version = entry.Version ?? "unknown",
            Description = entry.Description ?? entry.Summary,
            Published = entry.Published ?? DateTime.MinValue,
            IsDeprecated = entry.Deprecation != null,
            DeprecationMessage = entry.Deprecation?.Message,
            Vulnerabilities = entry.Vulnerabilities?.Select(v => $"{v.Severity}: {v.AdvisoryUrl}").ToList() ?? new(),
        };
    }
}
