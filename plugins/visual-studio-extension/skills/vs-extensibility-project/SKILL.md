---
name: vs-extensibility-project
description: 'Set up and build an out-of-process VisualStudio.Extensibility extension: choose out-of-process versus in-process hosting, configure commands in code, fix Extensibility SDK analyzer and build errors (CEE0028, CEE0027, CS0118, CA1416, CA1852, MC3050), embed Remote UI XAML, localize strings under .vsextension, configure test projects, and add settings. Use for project files, the Extension class, Command classes, and build failures in a VisualStudio.Extensibility project; not for deployment or theming.'
---

# VisualStudio.Extensibility Project and Build

Rules for structuring and building a `Microsoft.VisualStudio.Extensibility` extension that runs out of process. Rules tagged **observed in practice** come from real build and runtime failures and are not documented on Microsoft Learn; confirm them against the SDK version the repository pins.

## When not to use

- F5, Experimental Instance, packaging, or deployment problems: use `vs-extension-deployment`.
- Tool window colors and control styles: use `vs-extension-remote-ui-theming`.
- Remote UI data contracts, bound collections, and selection: use `vs-extension-remote-ui` (plugin `dotnet-azure-lessons`, if installed).
- Checking a package version before adding or updating it: use `nuget-validate` (plugin `nuget-validate`, if installed).

## Rules

### 1. Start out of process and justify any in-process fallback

- **Rule:** Use the out-of-process VisualStudio.Extensibility model by default. Move to in-process hosting (`RequiresInProcessHosting = true`, VSSDK compatibility) only for a named capability that the out-of-process APIs lack, and record that capability in the design.
- **Check:** The design names the missing API for every in-process component; the committed out-of-process project has no `Microsoft.VSSDK.BuildTools` or `Microsoft.VisualStudio.Sdk` reference.
- **Why:** Out-of-process extensions are isolated from Visual Studio crashes and can install without a restart, but the API surface is still smaller than VSSDK (Microsoft Learn).

### 2. Keep the target framework and SDK version pinned by the repository

- **Rule:** Use the target framework and `Microsoft.VisualStudio.Extensibility.*` version the repository already pins. Do not change either as a side effect of another task. Derive the minimum Visual Studio version in the manifest from that SDK version and the contributions the extension uses.
- **Check:** The diff changes no `TargetFramework` or Extensibility package version unless the task asks for an upgrade; the manifest minimum version is justified in the change description.
- **Why:** A minimum version copied from a sample, such as `[17.9,)`, claims support for Visual Studio versions that were never shown to load the extension.

### 3. Configure commands in code, not in .vsct

- **Rule:** For out-of-process commands, use `CommandConfiguration` placements, `MenuConfiguration`, `ToolbarConfiguration`, and `CommandGroupConfiguration`. Add a `.vsct` file only for an in-process component that requires one.
- **Check:** An out-of-process project contains no `.vsct` file.
- **Why:** Code-based configuration is the VisualStudio.Extensibility model; `.vsct` is a VSSDK concept (Microsoft Learn).

### 4. Use only placements that exist

- **Rule:** `CommandPlacement.KnownPlacements` offers `ToolsMenu`, `ViewOtherWindowsMenu`, and `ExtensionsMenu`. For other locations, use `CommandPlacement.VsctParent(guid, id, priority)` or a `CommandGroupConfiguration` with `GroupPlacement`.
- **Check:** Every `KnownPlacements` member in the code is one of the documented members; the command appears in the intended menu in the Experimental Instance.
- **Why:** A guessed member such as `KnownPlacements.ViewMenuMiddle` does not exist and fails to compile.

### 5. Provide Metadata when hosting out of process

- **Rule:** When `RequiresInProcessHosting` is `false` (the default), set `ExtensionConfiguration.Metadata` with `id`, `version` (`this.ExtensionAssemblyVersion`), `publisherName`, and `displayName`. When it is `true`, `Metadata` must be `null`.
- **Check:** The `Extension` subclass sets `Metadata` exactly when hosting out of process.
- **Why:** Microsoft Learn documents this rule. Observed in practice: a missing `Metadata` fails the build with CEE0028.

### 6. Centralize extension identity

- **Rule:** Define the extension ID, publisher, display name, and version in one place and reuse them in `Metadata`, settings paths, and startup diagnostics. Never write prompts, command arguments, secrets, or local paths to identity or startup logs.
- **Check:** A test or search shows that the C# metadata, the packaged manifest, and the deployed manifest carry the same identity, and that no former identity remains.
- **Why:** Observed in practice: a renamed identity left a second Experimental deployment that ran old code (see `vs-extension-deployment`).

### 7. Resolve the `Extension` name collision with an alias

- **Rule:** If the project's root namespace makes `Extension` ambiguous (for example a namespace ending in `.Extension`), alias the SDK namespace (`using VSX = Microsoft.VisualStudio.Extensibility;`) and write `VSX.Extension` and `VSX.VisualStudioContribution`.
- **Check:** The build has no CS0118 error and no cascading SDK generator error.
- **Why:** Observed in practice: CS0118 on `Extension` caused a cascade of SDK generator errors that hid the real cause.

### 8. Declare the supported OS once at the assembly level

- **Rule:** With `TreatWarningsAsErrors`, add one `[assembly: SupportedOSPlatform("windows<version>")]` matching the target framework's Windows version instead of per-member attributes.
- **Check:** The build has no CA1416 diagnostics, and only one assembly-level attribute exists.
- **Why:** Observed in practice: the Extensibility types are annotated as Windows-only, so every use raised CA1416 until the assembly declared its platform.

### 9. Localize display names with `%key%` resources under `.vsextension/`

- **Rule:** Pass `%Key%` tokens to `CommandConfiguration`, tool window titles, and other display strings. Put the default resources in `.vsextension/string-resources.json` and localized resources in `.vsextension/<culture>/string-resources.json`. Do not keep a copy at the project root.
- **Check:** The packaged VSIX contains `.vsextension/string-resources.json` and each culture folder, and the menu shows text rather than the raw `%Key%` token.
- **Why:** Microsoft Learn places localization files at `.vsextension/string-resources.json`. Observed in practice: a root-level file built successfully but was not packaged, so the menu showed the raw token, and analyzer CEE0027 flagged literal display strings in a project that treated warnings as errors.

### 10. Embed Remote UI XAML instead of compiling it

- **Rule:** For each Remote UI XAML file and resource dictionary, add `<Page Remove="..."/>` and `<EmbeddedResource Include="..."/>`, and set a `LogicalName` when the default resource name is not what the `RemoteUserControl` loads. A control's XAML root is a `DataTemplate` without `x:Class`; a shared dictionary registered with `ResourceDictionaries.AddEmbeddedResource` has a `ResourceDictionary` root.
- **Check:** The built assembly contains the XAML under the expected resource name; the project builds with `UseWPF` without MC3050 errors.
- **Why:** Microsoft Learn documents the `EmbeddedResource` and `Page Remove` pair. Observed in practice: compiling the XAML as a page tried to resolve Visual Studio Shell types that are not in the extension's compile graph and failed with MC3050.

### 11. Do not ship Visual Studio Shell assemblies

- **Rule:** Do not keep a `PackageReference` to `Microsoft.VisualStudio.Shell.15.0` in an out-of-process extension. A temporary reference for XAML editing must be removed before commit.
- **Check:** The project file and the packaged VSIX contain no Shell assembly.
- **Why:** Remote UI XAML is loaded in the Visual Studio process, which already has Shell; the extension must not depend on it (Microsoft Learn).

### 12. Seal concrete contribution classes

- **Rule:** Mark concrete `Extension`, `Command`, `ToolWindow`, and `RemoteUserControl` subclasses `sealed` unless they are derived from.
- **Check:** The build has no CA1852 diagnostics.
- **Why:** Observed in practice: with `latest-recommended` analysis and warnings as errors, unsealed internal classes failed the build.

### 13. Match test projects to the extension's target framework

- **Rule:** A test project that references the extension project uses the same Windows-specific target framework. Suppress `NU1603` or demote `MSB3277` only in that test project, and only after inspecting the resolved dependency graph and the runtime assembly version.
- **Check:** The test project's target framework equals the extension's; each suppression has a comment naming the inspected package or assembly.
- **Why:** Observed in practice: a test project without the Windows-specific target framework failed restore with NU1201. A suppression copied to other projects without that inspection can hide a real version conflict.

### 14. Use the VisualStudio.Extensibility settings API for options

- **Rule:** Define options with the VisualStudio.Extensibility settings contributions so that they appear in the Visual Studio settings experience. Do not add a VSSDK `DialogPage` to an out-of-process extension. Do not claim that a page appears in the new settings experience unless its registration exists and the page was seen there.
- **Check:** The settings appear under the extension's category in the Experimental Instance, and their values persist across a restart.
- **Why:** VisualStudio.Extensibility settings integrate with the unified settings experience (Microsoft Learn); a `DialogPage` requires an in-process package.

### 15. Build the VSIX manifest for both architectures

- **Rule:** When the repository authors manifest content, list `amd64` and `arm64` `ProductArchitecture` entries for each installation target, and mark pre-release builds as preview.
- **Check:** The packaged `extension.vsixmanifest` lists both architectures.
- **Why:** Visual Studio also runs natively on Arm64; a manifest that lists only `amd64` excludes those installations.
