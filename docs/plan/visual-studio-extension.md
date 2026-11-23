# Visual Studio Extension and WPF XAML Plugins

## Summary

`visual-studio-extension` holds checkable rules for out-of-process Visual Studio extensions built with VisualStudio.Extensibility and Remote UI. `wpf-xaml` holds WPF rules that also state their Remote UI exceptions. Remote UI binding, serialization, selection, and layout rules stay in `dotnet-azure-lessons/vs-extension-remote-ui`.

Tracking: [Issue #120](https://github.com/tfsugjp/skills/issues/120).

## Plugins and skills

| Plugin | Skill or agent | Scope |
|---|---|---|
| `visual-studio-extension` | `vs-extensibility-project` | Hosting choice, code-based commands, Extensibility SDK build errors, embedded Remote UI XAML, `.vsextension` localization, test project target framework, settings, VSIX manifest |
| `visual-studio-extension` | `vs-extension-deployment` | SDK-owned F5, LoaderLock MDA, duplicate Experimental Instance identities, packaged-VSIX validation, end-to-end hash comparison, `ActivityLog.xml`, VSIX lock handling |
| `visual-studio-extension` | `vs-extension-lifecycle` | Idempotent disposal, owned diagnostics readers, serialized worker start and stop, async-once cleanup |
| `visual-studio-extension` | `vs-extension-remote-ui-theming` | Automatic theming first, `ShellColors` tokens for Visual Studio 2026, `DynamicResource`, paired foreground and background states, re-based control styles, theme verification |
| `visual-studio-extension` | `vs-extension-oauth` | Public-client sign-in: inputs only when in scope, no client secret, MSAL silent-first, WAM broker with a parent window, PKCE for other providers, encrypted token cache |
| `visual-studio-extension` | Agent `vs-extension-reviewer` | Read-only diff review that routes to the skills above, `vs-extension-remote-ui`, `wpf-xaml`, and `nuget-validate`, and reports skills that are not installed |
| `wpf-xaml` | `wpf-xaml` | WPF applicability check, MVVM, CommunityToolkit.Mvvm, Dispatcher threading, virtualization, freezables, resources, theme colors, accessibility |
| `dotnet-azure-lessons` | `vs-extension-remote-ui` | Adds serialization rules (`[DataContract]`, `IAsyncCommand`, public `CanExecute`, data-context binding validation) and the `CanContentScroll` / virtualization tradeoff |

## Design decisions

- **Two plugins.** WPF-only projects can install `wpf-xaml` without Visual Studio extension rules.
- **One owner per rule.** Remote UI binding and serialization rules live only in `vs-extension-remote-ui`; theme keys and control styles live only in `vs-extension-remote-ui-theming`; general WPF rules live only in `wpf-xaml`. Other skills point to the owner.
- **References across plugins by name.** Each plugin can be installed alone and relative links may not leave a plugin root, so related skills are named with their plugin and marked "if installed".
- **Evidence labels.** A rule backed by Microsoft Learn says so in its reason. A rule that comes from observed failures and is not documented on Microsoft Learn, such as Extensibility SDK analyzer codes or SDK serialization internals, is tagged "observed in practice".
- **Current theme tokens.** Visual Studio 2026 replaced `EnvironmentColors`, `CommonControlsColors`, and `TreeViewColors` with `ShellColors`. New UI uses `ShellColors`; legacy keys remain only when the supported range includes older versions and every key is confirmed there.
- **Remote UI exceptions in WPF rules.** Generated `[RelayCommand]` commands are not `IAsyncCommand`, `[ObservableProperty]` fields need `[property: DataMember]`, and `StaticResource` preference, `Freeze`, and merged dictionaries do not apply to Remote UI shared resources.
- **No product-specific content.** Rules name no product, publisher, extension ID, class, or test of the project they came from, and pin no framework or SDK version; they refer to the versions the repository pins.
- **Approval gates.** Removing a former Experimental Instance identity requires approval for the exact targets; a full Experimental Instance reset requires separate approval. Stopping a process that locks the VSIX is limited to the process of the current build.
- **Conditional OAuth inputs.** Provider, client ID, authority, scopes, and redirect URI are asked for only when a task adds or changes sign-in.

## Verification

- `scripts/validate_marketplaces.py` passes.
- A search of the new and changed files finds no product-specific identifier from the source material.
- Every skill named by `vs-extension-reviewer` and `AGENTS.md` exists in this repository.
