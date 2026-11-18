#!/usr/bin/env dotnet
// mutation-run - run Stryker.NET once before opening a PR, limited to code changed versus the PR base
// branch, and summarize surviving mutants.
//
// Usage examples (file-based app, .NET 10+ SDK, no project file required):
//   dotnet run <skill-dir>/scripts/mutation-run.cs -- run --base main
//   dotnet run <skill-dir>/scripts/mutation-run.cs -- run --repo <repo-root> --base main --solution <repo-root>/App.slnx
//   dotnet run <skill-dir>/scripts/mutation-run.cs -- run --base main --json -- --concurrency 4
//   dotnet run <skill-dir>/scripts/mutation-run.cs -- summarize --report <repo-root>/StrykerOutput/pre-pr/reports/mutation-report.json
//
// Relative --solution and --output paths are resolved against the repository root, where Stryker runs.
// The helper owns the output directory: it deletes <output>/reports/mutation-report.json and .html before
// each run so that only a report written by that run is summarized.
//
// Exit codes: 0 success; 1 helper usage error, or a Stryker failure passed through (for example rejected
// options); 2 Stryker score below thresholds.break; 3 precondition or report error, including no fresh
// report after Stryker exited 0 (a report error never replaces a non-zero Stryker exit code); 4 diff mode fell back to a full run and was stopped; 5 timeout. Other
// Stryker exit codes are passed through unchanged.
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

const int ExitSuccess = 0;
const int ExitUsage = 1;
const int ExitPrecondition = 3;
const int ExitFullRunFallback = 4;
const int ExitTimeout = 5;
const int DefaultTimeoutMinutes = 30;
// One day; keeps the timer well inside Task.Delay and TimeSpan limits.
const int MaxTimeoutMinutes = 1440;
// How long to wait for the process exit and EOF on its output pipes (after a kill or a normal exit) before
// reporting the stop as unconfirmed or the output as not fully checked.
const int KillWaitSeconds = 30;
const string FallbackMarker = "Non-CSharp";
const string TestedBecauseMarker = "will be tested because:";
// Reasons Stryker's diff mode gives when it is limiting the run to changed code.
string[] knownDiffReasons = ["Mutant changed compared to target commit", "One or more covering tests changed"];

// Stryker options the helper sets itself; extra arguments after "--" may not override them.
ReservedOption[] reservedStrykerOptions =
[
    new("--since", null, false, "use the helper option --base <branch> instead."),
    new("--with-baseline", null, false, "use the helper option --base <branch> instead (baseline mode is not supported)."),
    new("--output", "-O", true, "use the helper option --output <dir> instead."),
    new("--reporter", "-r", false, "the helper always uses the Progress, Html, and Json reporters; this is not configurable."),
    new("--test-runner", "-t", false, "use the helper option --test-runner auto|vstest|mtp instead."),
    new("--solution", "-s", false, "use the helper option --solution <path> instead.")
];

string[] statusOrder =["Killed", "Survived", "NoCoverage", "Timeout", "CompileError", "RuntimeError", "Ignored", "Pending"];
var pathComparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
var ansiPattern = new Regex(@"\x1B\[[0-9;?]*[ -/]*[@-~]", RegexOptions.Compiled);

// Arguments after a standalone "--" are forwarded to Stryker untouched.
var allArgs = args.ToList();
var separatorIndex = allArgs.IndexOf("--");
var extraStrykerArgs = separatorIndex >= 0 ? allArgs.Skip(separatorIndex + 1).ToList() : [];
var commandArgs = separatorIndex >= 0 ? allArgs.Take(separatorIndex).ToList() : allArgs;

if (commandArgs.Count == 0 || commandArgs[0] is "-h" or "--help")
{
    PrintUsage(Console.Out);
    return ExitSuccess;
}

var command = commandArgs[0].ToLowerInvariant();
if (commandArgs.Skip(1).Any(a => a is "-h" or "--help"))
{
    PrintUsage(Console.Out);
    return ExitSuccess;
}

ParsedOptions options;
try
{
    options = ParseOptions(command, commandArgs.Skip(1).ToList(), extraStrykerArgs);
}
catch (UsageException ex)
{
    Console.Error.WriteLine($"Error: {ex.Message}");
    PrintUsage(Console.Error);
    return ExitUsage;
}

try
{
    return command switch
    {
        "run" => await RunAsync(options),
        "summarize" => Summarize(options),
        _ => ExitUsage
    };
}
catch (Exception ex)
{
    return Fail(options.Json, ExitPrecondition, $"Unexpected error: {ex.Message}");
}

ParsedOptions ParseOptions(string commandName, List<string> rest, List<string> extra)
{
    if (commandName is not ("run" or "summarize"))
    {
        throw new UsageException($"Unknown command '{commandName}'.");
    }

    var parsed = new ParsedOptions { ExtraStrykerArgs = extra, TimeoutMinutes = DefaultTimeoutMinutes };
    var valueOptions = commandName == "run"
        ? new HashSet<string> { "--repo", "--base", "--solution", "--output", "--timeout-minutes", "--test-runner" }
        : new HashSet<string> { "--report" };
    var flagOptions = commandName == "run"
        ? new HashSet<string> { "--allow-full-run", "--json" }
        : new HashSet<string> { "--json" };

    if (commandName == "summarize" && extra.Count > 0)
    {
        throw new UsageException("summarize does not accept extra Stryker arguments after '--'.");
    }

    // Extra Stryker arguments must not override the options the helper owns (diff base, output, reporters,
    // test runner, solution). Checked here so a rejected argument fails before any git or Stryker work.
    foreach (var argument in extra)
    {
        if (FindReservedStrykerOption(argument) is { } reserved)
        {
            throw new UsageException(
                $"Extra Stryker argument '{argument}' overrides the helper-owned option {reserved.Option}; {reserved.Instead}");
        }
    }

    for (var i = 0; i < rest.Count; i++)
    {
        var name = rest[i];
        if (flagOptions.Contains(name))
        {
            if (name == "--json") parsed.Json = true;
            if (name == "--allow-full-run") parsed.AllowFullRun = true;
            continue;
        }

        if (!valueOptions.Contains(name))
        {
            throw new UsageException($"Unknown option '{name}' for '{commandName}'.");
        }

        if (i + 1 >= rest.Count || rest[i + 1].StartsWith("--", StringComparison.Ordinal))
        {
            throw new UsageException($"Option '{name}' requires a value.");
        }

        var value = rest[++i];
        switch (name)
        {
            case "--repo": parsed.Repo = value; break;
            case "--base": parsed.Base = value; break;
            case "--solution": parsed.Solution = value; break;
            case "--output": parsed.Output = value; break;
            case "--report": parsed.Report = value; break;
            case "--timeout-minutes":
                if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var minutes) ||
                    minutes <= 0 || minutes > MaxTimeoutMinutes)
                {
                    throw new UsageException($"--timeout-minutes must be an integer from 1 to {MaxTimeoutMinutes}.");
                }

                parsed.TimeoutMinutes = minutes;
                break;
            case "--test-runner":
                var runner = value.ToLowerInvariant();
                if (runner is not ("auto" or "vstest" or "mtp"))
                {
                    throw new UsageException("--test-runner must be one of: auto, vstest, mtp.");
                }

                parsed.TestRunner = runner;
                break;
        }
    }

    if (commandName == "summarize" && string.IsNullOrWhiteSpace(parsed.Report))
    {
        throw new UsageException("summarize requires --report <path>.");
    }

    return parsed;
}

ReservedOption? FindReservedStrykerOption(string argument)
{
    foreach (var reserved in reservedStrykerOptions)
    {
        // Long names are matched case-insensitively as "--opt", "--opt:value", or "--opt=value".
        if (MatchesWithDelimiter(argument, reserved.Long, StringComparison.OrdinalIgnoreCase))
        {
            return reserved;
        }

        if (reserved.Short is not { } shortName)
        {
            continue;
        }

        // Short names are case-sensitive ("-o" is --open-report) and matched exactly or with ":"/"=", so that
        // multi-letter short names such as "-tp" (--test-project) stay allowed. "-O" also rejects "-Ovalue".
        if (MatchesWithDelimiter(argument, shortName, StringComparison.Ordinal) ||
            (reserved.AllowAttachedShortValue && argument.Length > shortName.Length &&
             argument.StartsWith(shortName, StringComparison.Ordinal)))
        {
            return reserved;
        }
    }

    return null;

    static bool MatchesWithDelimiter(string argument, string name, StringComparison comparison) =>
        argument.Equals(name, comparison) ||
        (argument.Length > name.Length &&
         argument.StartsWith(name, comparison) &&
         argument[name.Length] is ':' or '=');
}

async Task<int> RunAsync(ParsedOptions opt)
{
    // Progress messages go to stderr when --json is set so stdout carries exactly one JSON object.
    var log = opt.Json ? Console.Error : Console.Out;

    // Resolve and canonicalize the repository root through git, even when --repo is given.
    var repoProbe = opt.Repo is { Length: > 0 } repoArg ? Path.GetFullPath(repoArg) : Directory.GetCurrentDirectory();
    if (!Directory.Exists(repoProbe))
    {
        return Fail(opt.Json, ExitPrecondition, $"Repository path '{repoProbe}' does not exist.");
    }

    var topLevel = RunCapture("git", repoProbe, "-C", repoProbe, "rev-parse", "--show-toplevel");
    if (topLevel.ExitCode != 0 || string.IsNullOrWhiteSpace(topLevel.Stdout))
    {
        return Fail(opt.Json, ExitPrecondition, $"'{repoProbe}' is not inside a git repository. Pass --repo <path>.");
    }

    var repoRoot = Path.GetFullPath(topLevel.Stdout.Trim());

    // Resolve the base branch without touching the network.
    var baseBranch = opt.Base;
    if (string.IsNullOrWhiteSpace(baseBranch))
    {
        var head = RunCapture("git", repoRoot, "-C", repoRoot, "symbolic-ref", "--short", "refs/remotes/origin/HEAD");
        if (head.ExitCode != 0 || string.IsNullOrWhiteSpace(head.Stdout))
        {
            return Fail(opt.Json, ExitPrecondition,
                "Could not determine the default branch from refs/remotes/origin/HEAD. Pass the PR base branch with --base <branch>.");
        }

        baseBranch = head.Stdout.Trim();
        if (baseBranch.StartsWith("origin/", StringComparison.Ordinal))
        {
            baseBranch = baseBranch["origin/".Length..];
        }
    }
    else if (baseBranch.StartsWith("origin/", StringComparison.Ordinal))
    {
        baseBranch = baseBranch["origin/".Length..];
    }

    var verify = RunCapture("git", repoRoot, "-C", repoRoot, "rev-parse", "--verify", "--quiet", $"refs/remotes/origin/{baseBranch}");
    if (verify.ExitCode != 0)
    {
        return Fail(opt.Json, ExitPrecondition,
            $"Remote-tracking branch 'origin/{baseBranch}' was not found. Run 'git fetch origin {baseBranch}' and retry (this helper never fetches).");
    }

    // Stryker must be available as a local tool so the version is pinned per repository.
    var tools = RunCapture("dotnet", repoRoot, "tool", "list", "--local");
    if (tools.ExitCode != 0 || !Regex.IsMatch(tools.Stdout, @"(?im)^\s*dotnet-stryker\s"))
    {
        return Fail(opt.Json, ExitPrecondition, string.Join(Environment.NewLine,
            "dotnet-stryker is not installed as a local tool in this repository.",
            "Install it from the repository root (validate the version first, for example with the nuget-validate skill):",
            "  dotnet new tool-manifest            (skip if a tool manifest already exists)",
            "  dotnet tool install dotnet-stryker --version <validated-version>",
            "Note: SDK 11 creates dotnet-tools.json at the repository root; an existing .config/dotnet-tools.json is reused."));
    }

    var testRunner = opt.TestRunner == "auto" ? DetectTestRunner(repoRoot) : opt.TestRunner;
    // Stryker runs with the repository root as its working directory, so relative paths resolve there.
    var output = opt.Output is { Length: > 0 } outArg
        ? Path.GetFullPath(outArg, repoRoot)
        : Path.Combine(repoRoot, "StrykerOutput", "pre-pr");

    var strykerArgs = new List<string>
    {
        "tool", "run", "dotnet-stryker", "--",
        $"--since:origin/{baseBranch}",
        "--test-runner", testRunner,
        "--output", output,
        "--reporter", "Progress",
        "--reporter", "Html",
        "--reporter", "Json",
        "--skip-version-check"
    };
    if (opt.Solution is { Length: > 0 } solution)
    {
        strykerArgs.Add("--solution");
        strykerArgs.Add(Path.GetFullPath(solution, repoRoot));
    }

    strykerArgs.AddRange(opt.ExtraStrykerArgs);

    log.WriteLine($"Repository root: {repoRoot}");
    log.WriteLine($"Base: origin/{baseBranch}");
    log.WriteLine($"Test runner: {testRunner}{(opt.TestRunner == "auto" ? " (auto-detected from global.json)" : string.Empty)}");
    log.WriteLine($"Output: {output}");
    log.WriteLine($"Command: {BuildCommandDisplay("dotnet", strykerArgs)}");
    log.WriteLine();

    var startInfo = new ProcessStartInfo("dotnet")
    {
        WorkingDirectory = repoRoot,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false
    };
    foreach (var argument in strykerArgs)
    {
        startInfo.ArgumentList.Add(argument);
    }

    var changedFiles = new List<string>();
    var changedLock = new object();
    string? fallbackLine = null;
    var fallbackDetected = 0;
    var warnings = new List<string>();
    // Completed by the output handler when it stops a full-run fallback, so the main wait ends promptly.
    var fallbackSignal = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

    using var process = new Process { StartInfo = startInfo };

    void HandleLine(string? rawLine)
    {
        if (rawLine is null)
        {
            return;
        }

        lock (changedLock)
        {
            log.WriteLine(rawLine);
        }

        foreach (var segment in ansiPattern.Replace(rawLine, string.Empty).Split('\r'))
        {
            var line = segment.Trim();
            if (line.Length == 0)
            {
                continue;
            }

            var changedMatch = Regex.Match(line, @"Changed (?:test )?file\s+(?<path>.+)$");
            if (changedMatch.Success)
            {
                lock (changedLock)
                {
                    var path = changedMatch.Groups["path"].Value.Trim();
                    if (!changedFiles.Contains(path))
                    {
                        changedFiles.Add(path);
                    }
                }
            }

            var reasonIndex = line.IndexOf(TestedBecauseMarker, StringComparison.Ordinal);
            if (reasonIndex < 0)
            {
                continue;
            }

            if (line.Contains(FallbackMarker, StringComparison.Ordinal))
            {
                if (!opt.AllowFullRun && Interlocked.Exchange(ref fallbackDetected, 1) == 0)
                {
                    fallbackLine = line;
                    TryKill(process);
                    fallbackSignal.TrySetResult();
                }

                continue;
            }

            var reason = line[(reasonIndex + TestedBecauseMarker.Length)..].Trim();
            if (!knownDiffReasons.Any(known => reason.StartsWith(known, StringComparison.Ordinal)))
            {
                // An unrecognized reason may mean diff mode is not limiting the run; surface it without stopping.
                var warning = $"Diff mode may not be limiting the run; unrecognized reason: {line}";
                lock (changedLock)
                {
                    if (!warnings.Contains(warning))
                    {
                        warnings.Add(warning);
                        Console.Error.WriteLine($"Warning: {warning}");
                    }
                }
            }
        }
    }

    // Reads one redirected stream line by line. It never faults: after a kill or disposal the stream may throw,
    // and the bounded drain below reports whether the output was fully read.
    async Task PumpAsync(StreamReader reader)
    {
        try
        {
            while (await reader.ReadLineAsync() is { } line)
            {
                HandleLine(line);
            }
        }
        catch (Exception ex) when (ex is IOException or ObjectDisposedException or InvalidOperationException)
        {
            // The stream was closed underneath the reader.
        }
    }

    // The helper owns the output directory: remove reports from earlier runs so that only a report written
    // by this run can be summarized.
    var reportPath = Path.Combine(output, "reports", "mutation-report.json");
    foreach (var staleReport in new[] { reportPath, Path.ChangeExtension(reportPath, ".html") })
    {
        try
        {
            if (File.Exists(staleReport))
            {
                File.Delete(staleReport);
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return Fail(opt.Json, ExitPrecondition, $"Could not delete the previous report '{staleReport}': {ex.Message}");
        }
    }

    if (!process.Start())
    {
        return Fail(opt.Json, ExitPrecondition, "Failed to start 'dotnet tool run dotnet-stryker'.");
    }

    // Each stream gets its own reader task; Task.Run keeps a buffered stream from delaying the other reader
    // and the timeout timer.
    var readersTask = Task.WhenAll(
        Task.Run(() => PumpAsync(process.StandardOutput)),
        Task.Run(() => PumpAsync(process.StandardError)));

    // Without event-based reading, WaitForExitAsync completes on process exit only, not on pipe EOF.
    var exitTask = process.WaitForExitAsync();
    var timedOut = false;
    using (var timeoutCts = new CancellationTokenSource())
    {
        var timeoutTask = Task.Delay(TimeSpan.FromMinutes(opt.TimeoutMinutes), timeoutCts.Token);
        var first = await Task.WhenAny(exitTask, fallbackSignal.Task, timeoutTask);
        timeoutCts.Cancel();
        if (first == timeoutTask && !exitTask.IsCompleted)
        {
            timedOut = true;
            TryKill(process);
        }
    }

    // Drain both readers before deciding the result so that fallback detection has seen every line. Never wait
    // indefinitely: a surviving descendant can keep the output pipes open.
    var drainTask = Task.WhenAll(exitTask, readersTask);
    await Task.WhenAny(drainTask, Task.Delay(TimeSpan.FromSeconds(KillWaitSeconds)));
    var drained = drainTask.IsCompletedSuccessfully;

    var stopped = timedOut || Volatile.Read(ref fallbackDetected) == 1;
    // After a stop, confirmation requires both the process exit and EOF on its output pipes.
    var killConfirmed = !stopped || drained;
    if (!stopped && !drained)
    {
        var warning = $"Stryker's output did not close within {KillWaitSeconds} seconds after it exited; trailing output " +
                      "was not checked for a full-run fallback.";
        lock (changedLock)
        {
            warnings.Add(warning);
            Console.Error.WriteLine($"Warning: {warning}");
        }
    }

    var killStateMessage = killConfirmed
        ? string.Empty
        : $"{Environment.NewLine}Warning: the Stryker process tree could not be confirmed stopped within {KillWaitSeconds} seconds " +
          $"(process exited: {SafeHasExited(process)}). Check for leftover dotnet, testhost, or Stryker processes.";

    if (Volatile.Read(ref fallbackDetected) == 1)
    {
        List<string> files;
        lock (changedLock)
        {
            files = [.. changedFiles];
        }

        var message = new StringBuilder();
        message.AppendLine("Stopped: Stryker's diff mode fell back to testing all mutants (full run).");
        message.AppendLine($"Trigger: {fallbackLine}");
        message.AppendLine(files.Count > 0
            ? "Changed files reported by Stryker before the fallback:"
            : "Stryker did not list changed files before the fallback (raise --verbosity to see them).");
        var nonCSharpFiles = files.Where(f => !f.EndsWith(".cs", StringComparison.OrdinalIgnoreCase)).ToList();
        foreach (var file in files)
        {
            message.AppendLine(nonCSharpFiles.Contains(file) ? $"  {file}   <- non-C# (likely trigger)" : $"  {file}");
        }

        message.AppendLine("A non-C# file in a test project (for example a .csproj, global.json, or test data) differs from the base.");
        message.AppendLine("Options: commit or revert those files, add them to since.ignore-changes-in in stryker-config.json,");
        message.Append("or re-run with --allow-full-run to accept the full run.");
        message.Append(killStateMessage);

        return Fail(opt.Json, ExitFullRunFallback, message.ToString(), writer =>
        {
            writer.WriteBoolean("killConfirmed", killConfirmed);
            writer.WriteStartArray("changedFiles");
            foreach (var file in files)
            {
                writer.WriteStringValue(file);
            }

            writer.WriteEndArray();
            writer.WriteStartArray("nonCSharpFiles");
            foreach (var file in nonCSharpFiles)
            {
                writer.WriteStringValue(file);
            }

            writer.WriteEndArray();
            writer.WriteString("trigger", fallbackLine);
            WriteWarnings(writer);
        });
    }

    if (timedOut)
    {
        return Fail(opt.Json, ExitTimeout,
            $"Stryker did not finish within {opt.TimeoutMinutes} minutes and was stopped. Increase --timeout-minutes or narrow the scope." +
            killStateMessage,
            writer =>
            {
                writer.WriteBoolean("killConfirmed", killConfirmed);
                WriteWarnings(writer);
            });
    }

    var strykerExitCode = process.ExitCode;
    ReportSummary? summary = null;
    string? reportError = null;
    if (File.Exists(reportPath))
    {
        // Any report problem is captured here so it can never replace a non-zero Stryker exit code.
        try
        {
            summary = LoadSummary(reportPath, repoRoot);
        }
        catch (Exception ex)
        {
            reportError = $"Could not read '{reportPath}': {ex.Message}";
        }
    }
    else
    {
        reportError = $"No report found at '{reportPath}'.";
    }

    // A zero Stryker exit code without a fresh, readable report means there is nothing to summarize.
    var noFreshReport = strykerExitCode == 0 && reportError is not null;
    var exitCode = noFreshReport ? ExitPrecondition : strykerExitCode;
    var noTestedMutants = strykerExitCode == 0 && summary is { TestedMutants: 0 };
    var noTestedNotice = noTestedMutants
        ? $"No mutants were tested (no mutable C# changes versus origin/{baseBranch}); this is not evidence of test strength."
        : null;
    var statusMessage = noFreshReport
        ? "Stryker exited 0 but no fresh mutation report was written; nothing to summarize. If the diff has no mutable C# changes, there is nothing to test."
        : strykerExitCode switch
        {
            0 => "Stryker finished successfully.",
            2 => "Stryker finished: mutation score is below thresholds.break.",
            _ => $"Stryker exited with code {strykerExitCode}."
        };

    if (opt.Json)
    {
        WriteJson(writer =>
        {
            writer.WriteBoolean("succeeded", exitCode == 0);
            writer.WriteNumber("exitCode", exitCode);
            writer.WriteString("message", statusMessage);
            writer.WriteString("repoRoot", repoRoot);
            writer.WriteString("base", $"origin/{baseBranch}");
            writer.WriteString("testRunner", testRunner);
            writer.WriteString("output", output);
            writer.WriteNumber("strykerExitCode", strykerExitCode);
            if (reportError is not null)
            {
                writer.WriteString("reportError", reportError);
            }

            if (summary is not null)
            {
                writer.WriteNumber("testedMutants", summary.TestedMutants);
                if (noTestedNotice is not null)
                {
                    writer.WriteString("notice", noTestedNotice);
                }

                writer.WritePropertyName("summary");
                writer.WriteStartObject();
                WriteSummaryProperties(writer, summary);
                writer.WriteEndObject();
            }

            WriteWarnings(writer);
        });
    }
    else
    {
        Console.WriteLine();
        var statusWriter = noFreshReport ? Console.Error : Console.Out;
        statusWriter.WriteLine(noFreshReport ? $"Error: {statusMessage}" : statusMessage);
        if (summary is not null)
        {
            PrintSummary(summary, noTestedNotice);
        }
        else if (reportError is not null)
        {
            statusWriter.WriteLine(reportError);
        }

        if (warnings.Count > 0)
        {
            Console.Error.WriteLine($"Warnings ({warnings.Count}): review the warning lines above before trusting this result.");
        }
    }

    return exitCode;

    void WriteWarnings(Utf8JsonWriter writer)
    {
        List<string> snapshot;
        lock (changedLock)
        {
            snapshot = [.. warnings];
        }

        writer.WriteStartArray("warnings");
        foreach (var warning in snapshot)
        {
            writer.WriteStringValue(warning);
        }

        writer.WriteEndArray();
    }
}

int Summarize(ParsedOptions opt)
{
    var reportPath = Path.GetFullPath(opt.Report!);
    if (!File.Exists(reportPath))
    {
        return Fail(opt.Json, ExitPrecondition, $"Report '{reportPath}' was not found.");
    }

    var probe = RunCapture("git", Directory.GetCurrentDirectory(), "rev-parse", "--show-toplevel");
    var repoRoot = probe.ExitCode == 0 && !string.IsNullOrWhiteSpace(probe.Stdout)
        ? Path.GetFullPath(probe.Stdout.Trim())
        : null;

    ReportSummary summary;
    try
    {
        summary = LoadSummary(reportPath, repoRoot);
    }
    catch (Exception ex) when (ex is JsonException or InvalidDataException or IOException or UnauthorizedAccessException)
    {
        return Fail(opt.Json, ExitPrecondition, $"Report '{reportPath}' is not a valid Stryker mutation report: {ex.Message}");
    }

    var notice = summary.TestedMutants == 0
        ? "No mutants were tested; this is not evidence of test strength."
        : null;
    if (opt.Json)
    {
        WriteJson(writer =>
        {
            WriteSummaryProperties(writer, summary);
            if (notice is not null)
            {
                writer.WriteString("notice", notice);
            }
        });
    }
    else
    {
        PrintSummary(summary, notice);
    }

    return ExitSuccess;
}

ReportSummary LoadSummary(string reportPath, string? repoRoot)
{
    using var stream = File.OpenRead(reportPath);
    using var document = JsonDocument.Parse(stream);
    var root = document.RootElement;
    if (root.ValueKind != JsonValueKind.Object ||
        !root.TryGetProperty("files", out var files) ||
        files.ValueKind != JsonValueKind.Object)
    {
        throw new InvalidDataException("The root object has no 'files' object.");
    }

    var counts = statusOrder.ToDictionary(s => s, _ => 0, StringComparer.Ordinal);
    var survivors = new List<MutantInfo>();
    var reportWarnings = new List<string>();

    // Report keys may use the long path form while git may return a different spelling; compare canonical forms.
    var basePaths = new List<string>();
    if (repoRoot is not null)
    {
        basePaths.Add(repoRoot);
    }

    if (GetString(root, "projectRoot") is { Length: > 0 } projectRoot && TryGetFullPath(projectRoot) is { } projectRootFull)
    {
        basePaths.Add(projectRootFull);
    }

    foreach (var file in files.EnumerateObject())
    {
        // Malformed entries are skipped with a warning instead of failing the whole summary.
        if (file.Value.ValueKind != JsonValueKind.Object)
        {
            reportWarnings.Add($"Skipped file entry '{file.Name}': expected an object but found {file.Value.ValueKind}.");
            continue;
        }

        if (!file.Value.TryGetProperty("mutants", out var mutants) || mutants.ValueKind != JsonValueKind.Array)
        {
            reportWarnings.Add($"Skipped file entry '{file.Name}': 'mutants' is missing or is not an array.");
            continue;
        }

        var displayPath = ToDisplayPath(file.Name, basePaths);
        var index = -1;
        foreach (var mutant in mutants.EnumerateArray())
        {
            index++;
            if (mutant.ValueKind != JsonValueKind.Object)
            {
                reportWarnings.Add($"Skipped mutant #{index} in '{file.Name}': expected an object but found {mutant.ValueKind}.");
                continue;
            }

            var status = GetString(mutant, "status");
            if (status is null)
            {
                reportWarnings.Add($"Mutant #{index} in '{file.Name}' has no string 'status'; counted as Pending.");
                status = "Pending";
            }

            counts[status] = counts.GetValueOrDefault(status) + 1;

            if (status is not ("Survived" or "NoCoverage"))
            {
                continue;
            }

            var line = 0;
            var column = 0;
            if (GetObject(mutant, "location") is { } location && GetObject(location, "start") is { } start)
            {
                line = GetInt(start, "line");
                column = GetInt(start, "column");
            }
            else
            {
                reportWarnings.Add($"Mutant #{index} in '{file.Name}' has no valid 'location.start'; reported at 0:0.");
            }

            survivors.Add(new MutantInfo(
                displayPath,
                line,
                column,
                status,
                GetString(mutant, "mutatorName") ?? "unknown",
                GetString(mutant, "replacement") ?? string.Empty));
        }
    }

    survivors.Sort((a, b) =>
    {
        var byFile = string.Compare(a.File, b.File, StringComparison.OrdinalIgnoreCase);
        if (byFile != 0) return byFile;
        var byLine = a.Line.CompareTo(b.Line);
        return byLine != 0 ? byLine : a.Column.CompareTo(b.Column);
    });

    var detected = counts["Killed"] + counts["Timeout"];
    var denominator = detected + counts["Survived"] + counts["NoCoverage"];
    double? score = denominator == 0 ? null : Math.Round(detected * 100.0 / denominator, 2);

    Dictionary<string, int>? thresholds = null;
    if (root.TryGetProperty("thresholds", out var thresholdElement) && thresholdElement.ValueKind == JsonValueKind.Object)
    {
        thresholds = [];
        foreach (var property in thresholdElement.EnumerateObject())
        {
            if (property.Value.ValueKind == JsonValueKind.Number && property.Value.TryGetInt32(out var value))
            {
                thresholds[property.Name] = value;
            }
        }
    }

    return new ReportSummary(reportPath, counts, score, denominator, thresholds, survivors, reportWarnings);
}

string? TryGetFullPath(string path)
{
    if (!Path.IsPathRooted(path))
    {
        return null;
    }

    try
    {
        return Path.GetFullPath(path);
    }
    catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException)
    {
        return null;
    }
}

string ToDisplayPath(string reportedPath, List<string> basePaths)
{
    if (!Path.IsPathRooted(reportedPath))
    {
        return reportedPath.Replace('\\', '/');
    }

    if (TryGetFullPath(reportedPath) is not { } full)
    {
        return reportedPath;
    }

    foreach (var basePath in basePaths)
    {
        var prefix = Path.EndsInDirectorySeparator(basePath) ? basePath : basePath + Path.DirectorySeparatorChar;
        if (full.StartsWith(prefix, pathComparison))
        {
            return full[prefix.Length..].Replace('\\', '/');
        }
    }

    return reportedPath;
}

void PrintSummary(ReportSummary summary, string? notice)
{
    foreach (var warning in summary.Warnings)
    {
        Console.Error.WriteLine($"Warning: {warning}");
    }

    Console.WriteLine();
    Console.WriteLine($"Mutation report: {summary.Report}");
    Console.WriteLine("Counts: " + string.Join(", ", summary.Counts.Select(kv => $"{kv.Key}={kv.Value}")));
    Console.WriteLine($"Tested mutants (Killed+Timeout+Survived+NoCoverage): {summary.TestedMutants}");
    Console.WriteLine($"Score (killed+timeout over detected+undetected): {FormatScore(summary.Score)}");
    if (notice is not null)
    {
        Console.WriteLine($"Notice: {notice}");
    }
    if (summary.Thresholds is { Count: > 0 } thresholds)
    {
        Console.WriteLine("Thresholds: " + string.Join(", ", thresholds.Select(kv => $"{kv.Key}={kv.Value}")));
    }

    Console.WriteLine("Note: Stryker's own final mutation score line is authoritative; this value is recomputed from the report.");
    Console.WriteLine();

    if (summary.Survivors.Count == 0)
    {
        Console.WriteLine("No Survived or NoCoverage mutants.");
        return;
    }

    Console.WriteLine($"Survived / NoCoverage mutants ({summary.Survivors.Count}):");
    foreach (var mutant in summary.Survivors)
    {
        var replacement = mutant.Replacement.ReplaceLineEndings(" ");
        Console.WriteLine($"  [{mutant.Status}] {mutant.File}:{mutant.Line}:{mutant.Column}  {mutant.Mutator}  ->  {replacement}");
    }
}

void WriteSummaryProperties(Utf8JsonWriter writer, ReportSummary summary)
{
    writer.WriteString("report", summary.Report);
    writer.WritePropertyName("counts");
    writer.WriteStartObject();
    foreach (var (status, count) in summary.Counts)
    {
        writer.WriteNumber(status, count);
    }

    writer.WriteEndObject();
    writer.WriteNumber("testedMutants", summary.TestedMutants);

    if (summary.Score is { } score)
    {
        writer.WriteNumber("score", score);
    }
    else
    {
        writer.WriteNull("score");
    }

    writer.WriteString("scoreNote", "Recomputed as (Killed+Timeout)/(Killed+Timeout+Survived+NoCoverage)*100; Stryker's own final score line is authoritative.");

    if (summary.Thresholds is { } thresholds)
    {
        writer.WritePropertyName("thresholds");
        writer.WriteStartObject();
        foreach (var (name, value) in thresholds)
        {
            writer.WriteNumber(name, value);
        }

        writer.WriteEndObject();
    }

    writer.WriteStartArray("survivors");
    foreach (var mutant in summary.Survivors)
    {
        writer.WriteStartObject();
        writer.WriteString("file", mutant.File);
        writer.WriteNumber("line", mutant.Line);
        writer.WriteNumber("column", mutant.Column);
        writer.WriteString("status", mutant.Status);
        writer.WriteString("mutator", mutant.Mutator);
        writer.WriteString("replacement", mutant.Replacement);
        writer.WriteEndObject();
    }

    writer.WriteEndArray();

    writer.WriteStartArray("reportWarnings");
    foreach (var warning in summary.Warnings)
    {
        writer.WriteStringValue(warning);
    }

    writer.WriteEndArray();
}

string FormatScore(double? score) => score is { } value ? value.ToString("0.00", CultureInfo.InvariantCulture) + "%" : "n/a";

string DetectTestRunner(string repoRoot)
{
    var globalJson = Path.Combine(repoRoot, "global.json");
    if (!File.Exists(globalJson))
    {
        return "vstest";
    }

    try
    {
        using var document = JsonDocument.Parse(File.ReadAllText(globalJson), new JsonDocumentOptions
        {
            CommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true
        });
        if (document.RootElement.TryGetProperty("test", out var test) &&
            GetString(test, "runner") is { } runner &&
            runner.Equals("Microsoft.Testing.Platform", StringComparison.OrdinalIgnoreCase))
        {
            return "mtp";
        }
    }
    catch (JsonException)
    {
        // An unreadable global.json falls back to the VSTest default.
    }

    return "vstest";
}

int Fail(bool json, int exitCode, string message, Action<Utf8JsonWriter>? extra = null)
{
    if (json)
    {
        WriteJson(writer =>
        {
            writer.WriteBoolean("succeeded", false);
            writer.WriteNumber("exitCode", exitCode);
            writer.WriteString("message", message);
            extra?.Invoke(writer);
        });
    }
    else
    {
        Console.Error.WriteLine($"Error: {message}");
    }

    return exitCode;
}

void WriteJson(Action<Utf8JsonWriter> writeProperties)
{
    using var buffer = new MemoryStream();
    using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions
    {
        Indented = true,
        // Output is written to a console or file, never embedded in HTML, so relaxed escaping keeps it readable.
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    }))
    {
        writer.WriteStartObject();
        writeProperties(writer);
        writer.WriteEndObject();
    }

    Console.WriteLine(Encoding.UTF8.GetString(buffer.ToArray()));
}

void TryKill(Process process)
{
    try
    {
        if (!process.HasExited)
        {
            process.Kill(entireProcessTree: true);
        }
    }
    catch (InvalidOperationException)
    {
        // The process already exited.
    }
    catch (System.ComponentModel.Win32Exception)
    {
        // Some child processes may already be gone; the bounded wait reports whether the stop was confirmed.
    }
    catch (AggregateException)
    {
        // Killing part of the tree failed; the bounded wait reports whether the stop was confirmed.
    }
}

bool SafeHasExited(Process process)
{
    try
    {
        return process.HasExited;
    }
    catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
    {
        return false;
    }
}

CaptureResult RunCapture(string fileName, string workingDirectory, params string[] arguments)
{
    var startInfo = new ProcessStartInfo(fileName)
    {
        WorkingDirectory = workingDirectory,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false
    };
    foreach (var argument in arguments)
    {
        startInfo.ArgumentList.Add(argument);
    }

    try
    {
        using var process = Process.Start(startInfo) ?? throw new InvalidOperationException($"Failed to start {fileName}.");
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        process.WaitForExit();
        return new CaptureResult(process.ExitCode, stdoutTask.Result, stderrTask.Result);
    }
    catch (System.ComponentModel.Win32Exception ex)
    {
        return new CaptureResult(-1, string.Empty, $"'{fileName}' could not be started: {ex.Message}");
    }
}

string? GetString(JsonElement element, string propertyName) =>
    element.ValueKind == JsonValueKind.Object &&
    element.TryGetProperty(propertyName, out var value) &&
    value.ValueKind == JsonValueKind.String
        ? value.GetString()
        : null;

JsonElement? GetObject(JsonElement element, string propertyName) =>
    element.ValueKind == JsonValueKind.Object &&
    element.TryGetProperty(propertyName, out var value) &&
    value.ValueKind == JsonValueKind.Object
        ? value
        : null;

int GetInt(JsonElement element, string propertyName) =>
    element.ValueKind == JsonValueKind.Object &&
    element.TryGetProperty(propertyName, out var value) &&
    value.ValueKind == JsonValueKind.Number &&
    value.TryGetInt32(out var number)
        ? number
        : 0;

string BuildCommandDisplay(string fileName, IEnumerable<string> arguments) =>
    string.Join(" ", new[] { fileName }.Concat(arguments.Select(QuoteArgument)));

string QuoteArgument(string argument)
{
    if (argument.Length == 0)
    {
        return "\"\"";
    }

    var needsQuoting = argument.Any(char.IsWhiteSpace) || argument.Contains('"') || argument.Contains('\'');
    return needsQuoting ? "\"" + argument.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"" : argument;
}

void PrintUsage(TextWriter writer)
{
    writer.WriteLine("""
    mutation-run - run Stryker.NET on the changes versus the PR base branch and summarize surviving mutants

    Usage:
      dotnet run scripts/mutation-run.cs -- run [--repo <path>] [--base <branch>] [--solution <path>]
          [--output <dir>] [--timeout-minutes <n>] [--allow-full-run] [--test-runner auto|vstest|mtp]
          [--json] [-- <extra stryker args>]
      dotnet run scripts/mutation-run.cs -- summarize --report <mutation-report.json> [--json]

    run:
      --repo             Repository root (default: git rev-parse --show-toplevel from the current directory).
      --base             PR base branch (default: refs/remotes/origin/HEAD). origin/<base> must already be fetched.
      --solution         Solution passed to Stryker (default: stryker-config.json or Stryker's own discovery).
                         A relative path is resolved against the repository root, not the current directory.
      --output           Output directory (default: <repo>/StrykerOutput/pre-pr, overwritten each run).
                         A relative path is resolved against the repository root, not the current directory.
      --timeout-minutes  Stop Stryker after this many minutes (1-1440, default: 30).
      --allow-full-run   Continue when Stryker's diff mode falls back to testing all mutants.
      --test-runner      auto (default; mtp when global.json test.runner is Microsoft.Testing.Platform), vstest, mtp.
      -- <args>          Extra arguments passed to Stryker unchanged, except helper-owned options, which are
                         rejected (exit 1) in any form (--opt value, --opt:value, --opt=value):
                           --since, --with-baseline   use --base
                           --output, -O               use --output
                           --reporter, -r             fixed to Progress, Html, Json
                           --test-runner, -t          use --test-runner
                           --solution, -s             use --solution

    Exit codes:
      0 success
      1 helper usage error, or a Stryker failure passed through (for example rejected options)
      2 score below thresholds.break (from Stryker)
      3 precondition or report error, including no fresh report after Stryker exited 0
      4 full-run fallback stopped
      5 timeout
      Other Stryker exit codes are passed through unchanged.
    After a timeout or fallback stop, the helper waits at most 30 seconds for the process tree; if the stop
    cannot be confirmed it says so (--json: "killConfirmed": false) and still exits 5 or 4.
    The previous mutation-report.json/.html in <output>/reports is deleted before Stryker starts.
    Exit 0 with "testedMutants": 0 means no mutant was tested; that is not evidence of test strength.
    Warnings: a "will be tested because:" line with an unrecognized reason is reported on stderr (and in
    --json output as "warnings") because diff mode may not be limiting the run; the run is not stopped.
    """);
}

public sealed class ParsedOptions
{
    public bool Json { get; set; }
    public bool AllowFullRun { get; set; }
    public string? Repo { get; set; }
    public string? Base { get; set; }
    public string? Solution { get; set; }
    public string? Output { get; set; }
    public string? Report { get; set; }
    public int TimeoutMinutes { get; set; }
    public string TestRunner { get; set; } = "auto";
    public List<string> ExtraStrykerArgs { get; set; } = [];
}

public sealed class UsageException(string message) : Exception(message);

public sealed record ReservedOption(string Long, string? Short, bool AllowAttachedShortValue, string Instead)
{
    public string Option => Short is null ? Long : $"{Long} ({Short})";
}

public sealed record CaptureResult(int ExitCode, string Stdout, string Stderr);

public sealed record MutantInfo(string File, int Line, int Column, string Status, string Mutator, string Replacement);

public sealed record ReportSummary(
    string Report,
    Dictionary<string, int> Counts,
    double? Score,
    int TestedMutants,
    Dictionary<string, int>? Thresholds,
    List<MutantInfo> Survivors,
    List<string> Warnings);
