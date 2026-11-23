---
name: wpf-xaml
description: 'WPF and Visual Studio Remote UI XAML rules for MVVM, data binding, CommunityToolkit.Mvvm, Dispatcher threading, UI virtualization, freezables, resources, theme colors, and accessibility, with explicit exceptions for Remote UI. Use only after confirming the project is WPF (UseWPF, WPF assemblies, or a VisualStudio.Extensibility Remote UI DataTemplate); not for .NET MAUI, WinUI 3, or UWP XAML.'
---

# WPF XAML

Rules for WPF views and view models, and for Remote UI XAML, which Visual Studio renders with WPF. Remote UI runs the XAML in another process, so several plain-WPF rules change; each rule states its Remote UI exception.

## When not to use

- .NET MAUI (`UseMaui`, the `http://schemas.microsoft.com/dotnet/2021/maui` namespace), WinUI 3 (`UseWinUI`, `Microsoft.WindowsAppSDK`), or UWP (`Windows.UI.Xaml`): stop and say the project is not WPF.
- Remote UI data contracts, collections, selectors, and XAML limits: use `vs-extension-remote-ui` (plugin `dotnet-azure-lessons`, if installed).
- Visual Studio theme keys and control styles: use `vs-extension-remote-ui-theming` (plugin `visual-studio-extension`, if installed).

## Rules

### 1. Confirm WPF from the project, not from the XAML

- **Rule:** Before applying any rule here, confirm WPF from project evidence: `<UseWPF>true</UseWPF>`, references to `PresentationFramework`, `PresentationCore`, or `WindowsBase`, or a Remote UI `DataTemplate` in a VisualStudio.Extensibility project. If the project file does not decide it, ask.
- **Check:** The answer names the project property or reference that proves WPF.
- **Why:** WPF and WinUI 3 share the default XAML namespace, and Dispatcher, `Freezable`, virtualization, and `DynamicResource` advice is wrong or different elsewhere.

### 2. Keep MVVM layers separate

- **Rule:** Models hold data and business logic without view or view-model dependencies. Views hold XAML bindings; code-behind handles only pure UI concerns such as focus. View models expose bindable state and commands and call services.
- **Check:** Code-behind contains no data access or business logic; models reference no WPF types.
- **Why:** Logic in code-behind cannot be tested and cannot move to Remote UI, which has no code-behind (Microsoft Learn).

### 3. Use CommunityToolkit.Mvvm in WPF, but not for Remote UI commands

- **Rule:** In plain WPF, prefer `ObservableObject` with `[ObservableProperty]` and `[RelayCommand]`; async command methods return `Task`, never `async void`, and accept a `CancellationToken` when they can run long. In a Remote UI data context, do not bind generated `[RelayCommand]` commands: expose `IAsyncCommand` (for example `AsyncCommand`) instead, and put `[property: DataMember]` on `[ObservableProperty]` fields of a `[DataContract]` type. Validate any new package version first (`nuget-validate`, if installed).
- **Check:** Remote UI view models expose only `IAsyncCommand` commands and every generated bound property carries `DataMember`.
- **Why:** Remote UI serializes only `DataMember` properties and commands that implement `IAsyncCommand` (Microsoft Learn); generated `[RelayCommand]` commands implement `ICommand`, so binding them fails.

### 4. Use observable collections and collection views

- **Rule:** Bind lists to `ObservableCollection<T>` (or `ObservableList<T>` in Remote UI) whose items implement `INotifyPropertyChanged`. In plain WPF, sort, filter, and group with `ICollectionView` or `CollectionViewSource` instead of copying the collection. In Remote UI, shape the collection in the view model and update it by identity (see `vs-extension-remote-ui`).
- **Check:** No view model replaces a bound collection instance to refresh it.
- **Why:** Replacing the collection loses selection and scroll position.

### 5. Touch UI objects only from their Dispatcher thread

- **Rule:** In plain WPF, run blocking or CPU-bound work with `await Task.Run(...)` and update UI after the `await`. Use `Dispatcher.InvokeAsync` when another thread must update UI; never call `Wait()` or `.Result` on a `DispatcherOperation` task. Report progress with `IProgress<T>`. In Remote UI, the extension has no WPF objects to marshal: update the data context, and pass a `SynchronizationContext` to the `RemoteUserControl` when commands and property updates must run on one extension thread.
- **Check:** No code blocks on a Dispatcher operation, and no WPF object is touched from a worker thread.
- **Why:** A `DispatcherObject` belongs to its creating thread, and waiting synchronously on a dispatcher operation deadlocks (Microsoft Learn).

### 6. Keep UI virtualization on for large lists

- **Rule:** Bind `ItemsSource` instead of adding item containers, keep a virtualizing items panel, give the list a bounded height (not an unbounded `StackPanel` or outer `ScrollViewer`), and use `VirtualizingStackPanel.VirtualizationMode="Recycling"` for long lists. Setting `ScrollViewer.CanContentScroll="False"` disables virtualization; use it only for short lists of tall, wrapped items, and say so.
- **Check:** Large lists keep a virtualizing panel and a bounded host; any `CanContentScroll="False"` has a comment on why the list stays short.
- **Why:** These conditions silently turn virtualization off and create every container (Microsoft Learn). Pixel scrolling for tall wrapped items is the documented tradeoff in `vs-extension-remote-ui`.

### 7. Freeze unchanging freezables in plain WPF

- **Rule:** Freeze brushes, pens, geometries, and transforms that will not change, after checking `CanFreeze`. Share them as resources instead of declaring them inline per element. This rule does not apply to Remote UI XAML, whose theme brushes are dynamic resources owned by Visual Studio.
- **Check:** Brushes created in code call `Freeze()`; repeated inline brushes are moved to resources.
- **Why:** A frozen freezable skips change notification and can be shared across threads (Microsoft Learn); a freezable with a `DynamicResource` or binding cannot be frozen.

### 8. Choose StaticResource and DynamicResource by whether the value changes

- **Rule:** In plain WPF, use `StaticResource` for values fixed after load and `DynamicResource` for theme colors, system colors, and runtime-swapped values. Never make a forward `StaticResource` reference. In Remote UI, reference your own resource dictionaries and all theme keys with `DynamicResource`.
- **Check:** Every theme or system color uses `DynamicResource`; no `StaticResource` refers to a key defined later.
- **Why:** `StaticResource` snapshots the value at load and does not follow theme changes (Microsoft Learn). Remote UI documents `DynamicResource` for resources added with `ResourceDictionaries.AddEmbeddedResource`.

### 9. Share styles through resource dictionaries the platform supports

- **Rule:** In plain WPF, factor shared styles into dictionaries merged with `ResourceDictionary.MergedDictionaries` (the last merged dictionary wins), extend styles with `BasedOn`, and use `TemplateBinding` inside control templates. In Remote UI, merged dictionaries are not supported: register each dictionary with `ResourceDictionaries.AddEmbeddedResource` in the `RemoteUserControl` constructor.
- **Check:** No Remote UI XAML contains `MergedDictionaries`.
- **Why:** Remote UI references dictionaries by embedded resource name, not through merged dictionaries (Microsoft Learn).

### 10. Never hard-code colors; pair foreground and background

- **Rule:** Do not write `Foreground="Black"`, `Background="#E6E6E6"`, or `Brushes.White`. Choose foreground and background as pairs from the same surface (for example `SystemColors.WindowTextBrushKey` with `SystemColors.WindowBrushKey`) through `DynamicResource`. Inside Visual Studio, use Visual Studio theme keys, not `SystemColors` (see `vs-extension-remote-ui-theming`).
- **Check:** A search finds no literal colors in views; each explicit foreground has a matching background from the same surface.
- **Why:** Hard-coded colors and mismatched pairs produce unreadable text in dark and high-contrast themes (Microsoft Learn).

### 11. Make every view accessible

- **Rule:** Set `AutomationProperties.Name` on interactive elements whose purpose is not given by visible text (icon-only buttons, images). Keep a logical tab order, visible focus, and no keyboard traps. Do not convey state by color alone. Custom interactive controls provide an `AutomationPeer`.
- **Check:** Every view is usable with the keyboard alone and in a high-contrast theme, and icon-only buttons have automation names.
- **Why:** Standard WPF controls support UI Automation only when they are given names and kept keyboard reachable (Microsoft Learn).
