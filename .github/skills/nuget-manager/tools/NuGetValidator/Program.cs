using System.Text.Json;
using NuGetValidator.Models;
using NuGetValidator.Services;

var commandArgs = args;

if (commandArgs.Length == 0)
{
    PrintUsage();
    return;
}

var command = commandArgs[0].ToLowerInvariant();

try
{
    var apiClient = new NuGetApiClient();
    var validationService = new ValidationService(apiClient);

    if (command == "validate" && commandArgs.Length >= 3)
    {
        var packageId = commandArgs[1];
        var version = commandArgs[2];
        var outputFormat = commandArgs.Length > 3 && commandArgs[3] == "--json" ? "json" : "text";

        Console.WriteLine($"Validating {packageId} {version}...");

        var result = await validationService.ValidatePackageAsync(packageId, version);

        if (outputFormat == "json")
        {
            var json = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
            Console.WriteLine(json);
        }
        else
        {
            PrintValidationResult(result);
        }

        Environment.Exit(result.IsValid ? 0 : 1);
    }
    else if (command == "latest" && commandArgs.Length >= 2)
    {
        var packageId = commandArgs[1];
        Console.WriteLine($"Finding latest safe version for {packageId}...");

        var latestVersion = await validationService.FindLatestSafeVersionAsync(packageId);

        if (latestVersion != null)
        {
            Console.WriteLine($"Latest safe version: {latestVersion}");
        }
        else
        {
            Console.WriteLine("No safe version found.");
            Environment.Exit(1);
        }
    }
    else if (command == "versions" && commandArgs.Length >= 2)
    {
        var packageId = commandArgs[1];
        Console.WriteLine($"Fetching versions for {packageId}...");

        var versions = await apiClient.GetPackageVersionsAsync(packageId);
        foreach (var v in versions.OrderByDescending(v => ParseVersion(v)))
        {
            Console.WriteLine(v);
        }
    }
    else
    {
        PrintUsage();
    }
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Error: {ex.Message}");
    if (commandArgs.Contains("--verbose"))
    {
        Console.Error.WriteLine(ex.StackTrace);
    }
    Environment.Exit(1);
}

void PrintValidationResult(ValidationResult result)
{
    Console.WriteLine($"\nPackage: {result.Package.PackageId} {result.Package.Version}");
    Console.WriteLine($"Published: {result.Package.Published:yyyy-MM-dd}");
    Console.WriteLine($"Days since published: {result.DaysSincePublished}");
    Console.WriteLine();

    if (result.Issues.Count == 0)
    {
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("✓ Package is valid and safe to use.");
        Console.ResetColor();
    }
    else
    {
        Console.WriteLine("Issues found:");
        foreach (var issue in result.Issues)
        {
            var color = issue.Severity switch
            {
                IssueSeverity.Error => ConsoleColor.Red,
                IssueSeverity.Warning => ConsoleColor.Yellow,
                _ => ConsoleColor.Cyan
            };

            Console.ForegroundColor = color;
            Console.WriteLine($"  [{issue.Severity}] {issue.Message}");
            Console.ResetColor();
        }
    }
}

void PrintUsage()
{
    Console.WriteLine("NuGetValidator - Validate NuGet packages for vulnerabilities and freshness");
    Console.WriteLine();
    Console.WriteLine("Usage:");
    Console.WriteLine("  NuGetValidator validate <package-id> <version> [--json] [--verbose]");
    Console.WriteLine("  NuGetValidator latest <package-id>");
    Console.WriteLine("  NuGetValidator versions <package-id>");
    Console.WriteLine();
    Console.WriteLine("Examples:");
    Console.WriteLine("  NuGetValidator validate Newtonsoft.Json 13.0.3");
    Console.WriteLine("  NuGetValidator validate Serilog 3.0.0 --json");
    Console.WriteLine("  NuGetValidator latest Newtonsoft.Json");
    Console.WriteLine("  NuGetValidator versions Newtonsoft.Json");
}

Version ParseVersion(string versionString)
{
    try
    {
        var basePart = versionString.Split('-')[0];
        return Version.Parse(basePart);
    }
    catch
    {
        return new Version(0, 0, 0);
    }
}
