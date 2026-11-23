---
name: vs-extension-remote-ui
description: 'Prevent silent binding failures, selection races, and layout defects in VisualStudio.Extensibility Remote UI. Use for RemoteUserControl data contracts, bound collections, selectors, or Remote UI XAML; not ordinary WPF or Avalonia views.'
---

# Visual Studio Extension Remote UI

Remote UI serializes view models across processes. Validate serialization and asynchronous write-back as well as local property values.

## When not to use

- Async, parsing, and collection rules that are not specific to Remote UI: use `dotnet-coding`.
- Deciding whether a change is verified in general: use `dotnet-testing`.
- Theme colors and control styles: use `vs-extension-remote-ui-theming` (plugin `visual-studio-extension`, if installed).
- General WPF binding, threading, virtualization, and accessibility: use `wpf-xaml` (plugin `wpf-xaml`, if installed).

## Rules

### 1. Expose every bound member as a data member

- **Rule:** Every property and command that XAML binds to has `[DataMember]` on a `[DataContract]` view model and raises change notification.
- **Check:** Search the XAML bindings and confirm each target has `[DataMember]`; confirm it appears in the running UI.
- **Why:** Missing data members made lists and commands unreachable from XAML without a binding exception.

### 2. Update ItemsSource collections by diff, not by rebuild

- **Rule:** When refreshing a bound list whose selection should survive, merge items by identity with `Insert`, `Move`, and `RemoveAt` rather than clearing and re-adding. Preserve existing item instances and update their order.
- **Check:** A test merges a reordered list and asserts both contents and order; the selected item stays selected in the IDE.
- **Why:** Rebuilding invalidated selection; a partial diff fix retained the wrong order.

### 3. Guard null write-back from selectors conditionally

- **Rule:** A two-way bound selection can write `null` back asynchronously while its collection changes. Ignore that `null` only when the current selection is still a valid item; accept it otherwise.
- **Check:** Tests cover a `null` write-back while the selection is valid (ignored) and after the selected item was removed (accepted).
- **Why:** A guard that ignored `null` whenever the list was non-empty kept an invalid selection.

### 4. Stay inside the Remote UI XAML limits

- **Rule:** Remote UI XAML is a single `DataTemplate` instantiated in the Visual Studio process. It cannot use code-behind, event-handler attributes, merged dictionaries, or types from the extension assembly (including custom controls). Express behavior through async commands and bindings; attach commands to events with `vs:ExtensibilityUICommands.EventHandlers`; share resources by adding a resource dictionary with `ResourceDictionaries.AddEmbeddedResource` in the `RemoteUserControl` and referencing it with `DynamicResource`.
- **Check:** The XAML has no `x:Class`, no event attributes, no `MergedDictionaries`, and no extension-assembly types.
- **Why:** Plans that relied on code-behind had to be redesigned.

### 5. Disable horizontal scrolling around wrapped text in lists

- **Rule:** For a `ListBox` or `ItemsControl` with wrapping `TextBlock` items, set `ScrollViewer.HorizontalScrollBarVisibility="Disabled"`. Consider `ScrollViewer.CanContentScroll="False"` for tall items only when the list stays short: it switches to pixel scrolling and disables UI virtualization.
- **Check:** A screenshot after a long response shows the full text and that the list scrolls to the end.
- **Why:** With horizontal scrolling on Auto, items were measured with infinite width, and long responses were cut off and could not be scrolled fully.

### 6. Use a selector for settings with a finite set of values

- **Rule:** For a closed set of setting values, use a selector with readable labels. Preserve editable input when custom values are part of the contract.
- **Check:** Supported choices are discoverable and unsupported values cannot be submitted for a closed set.
- **Why:** A free-text language field accepting `auto`, `ja`, or `en` was unclear to the user and was replaced by a selector.

### 7. Verify in the Experimental instance, including visual states

- **Rule:** Validate the changed path in the target Experimental instance using the new build (`dotnet-testing`, "Judge UI changes from screenshots"). Check affected selection, disabled, narrow-width, theme, or language states. If the IDE is unavailable, report that gap; local tests do not prove the remote UI works.
- **Check:** Observed states have screenshot verdicts; required unobserved states remain explicit gaps. Response controls stay reachable at narrow widths.
- **Why:** Compilation and local tests missed cut-off controls and incorrect visual states in the real IDE.

### 8. Know what Remote UI can serialize

- **Rule:** Every data context type, including nested view models and types from shared contract assemblies, has `[DataContract]`, and every bound property has `[DataMember]`. Commands implement `IAsyncCommand`, not only `ICommand`. Bind enums as their names (observed in practice). When a shared type gains `[DataContract]`, mark every property that other serializers (for example Newtonsoft.Json over JSON-RPC) must keep with `[DataMember]`.
- **Check:** A test enumerates the data context type graph and asserts `[DataContract]` on each type, `[DataMember]` on each bound property, and `IAsyncCommand` on each command.
- **Why:** Only primitives, `[DataContract]` types, `IAsyncCommand` objects, `XamlFragment`, `SolidColorBrush`, `Color`, nullable values, and collections of these are serializable (Microsoft Learn). Observed in practice: a type without `[DataContract]` was sent as an empty object, so every binding to it stayed blank without an error, and an `ICommand`-only property threw `NotSupportedException` and stopped the whole data context from being set. Newtonsoft.Json switches to opt-in serialization for `[DataContract]` types, so unmarked properties disappeared from worker RPC.

### 9. Expose CanExecute as a public property

- **Rule:** The SDK's `AsyncCommand` already satisfies this rule. On a custom `IAsyncCommand`, implement `CanExecute` as a public property and raise `PropertyChanged` for it when executability changes. If the class also implements `ICommand`, implement `ICommand.CanExecute(object?)` explicitly. Catch and log exceptions thrown while applying view model changes from notifications.
- **Check:** Reflection finds a public `CanExecute` property on every command type.
- **Why:** Observed in practice: with an explicitly implemented `CanExecute` property, the change notification could not resolve the property and threw inside the RPC dispatch loop; all later notifications stopped and the tool window froze in its last state with no visible error.

### 10. Validate every data-context binding, and only those

- **Rule:** Validation of XAML bindings against `[DataMember]` covers every binding path that reaches the Remote UI data context, including nested view models and paths that select an element through `RelativeSource` or `ElementName` and then read its `DataContext` (for example `DataContext.RemoveCommand`). Exclude only bindings that stay in the WPF tree, such as `TemplateBinding` or a `RelativeSource` path to an element property like `IsSelected`. Keep nested view models when they serialize and notify correctly; do not flatten them into the root without evidence.
- **Check:** A test parses the embedded XAML, resolves each binding that reaches the data context (directly or through an element's `DataContext`), and asserts its root is a `[DataMember]`; a nested `PropertyChanged` and collection Reset/Add are verified before blaming rendering.
- **Why:** Excluding too much hides missing data members, and excluding too little fails on tree-relative bindings that never touch the data context.
