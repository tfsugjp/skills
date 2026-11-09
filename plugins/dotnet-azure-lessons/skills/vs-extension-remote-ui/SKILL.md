---
name: vs-extension-remote-ui
description: 'Rules for Visual Studio extensions built on VisualStudio.Extensibility Remote UI (RemoteUserControl, data contracts, XAML), learned from bindings that failed silently and layouts that broke only in the real IDE. Use while editing a Remote UI view model, adding [DataMember] properties or commands, updating an ObservableCollection bound to an ItemsSource or ComboBox, editing Remote UI XAML, adding a settings field, or verifying an extension change in the Experimental instance. Not for general C# rules (dotnet-coding).'
---

# Visual Studio Extension Remote UI

Remote UI view models live in the extension process and are serialized to Visual Studio. Many mistakes do not throw: the binding is simply empty, or a value is written back asynchronously. Unit tests and builds miss these; the Experimental instance does not.

## When not to use

- Async, parsing, and collection rules that are not specific to Remote UI: use `dotnet-coding`.
- Deciding whether a change is verified in general: use `dotnet-testing`.

## Rules

### 1. Expose every bound member as a data member

- **Rule:** Every property and command that XAML binds to has `[DataMember]` on a `[DataContract]` view model and raises change notification.
- **Check:** Search the XAML bindings and confirm each target has `[DataMember]`; confirm it appears in the running UI.
- **Why:** Members without `[DataMember]` serialize as empty, and the binding fails silently. A profile list and its commands were unreachable from XAML until this was fixed.

### 2. Update ItemsSource collections by diff, not by rebuild

- **Rule:** Merge a new list into a bound `ObservableCollection` with `Insert`, `Move`, and `RemoveAt`. Do not `Clear()` and re-add, and fix the order of existing items with `Move`.
- **Check:** A test merges a reordered list and asserts both contents and order; the selected item stays selected in the IDE.
- **Why:** Clear-and-add made the IDE's `ComboBox` selection invalid, and the default model disappeared from the dropdown. The first diff fix still did not reorder existing items.

### 3. Guard null write-back from selectors conditionally

- **Rule:** A two-way bound selection can write `null` back asynchronously while its collection changes. Ignore that `null` only when the current selection is still a valid item; accept it otherwise.
- **Check:** Tests cover a `null` write-back while the selection is valid (ignored) and after the selected item was removed (accepted).
- **Why:** A guard that ignored `null` whenever the list was non-empty kept an invalid selection.

### 4. Stay inside the Remote UI XAML limits

- **Rule:** Remote UI XAML is a single `DataTemplate` instantiated in the Visual Studio process. It cannot use code-behind, event-handler attributes, merged dictionaries, or types from the extension assembly (including custom controls). Express behavior through async commands and bindings; attach commands to events with `vs:ExtensibilityUICommands.EventHandlers`; share resources by adding a resource dictionary with `ResourceDictionaries.AddEmbeddedResource` in the `RemoteUserControl` and referencing it with `DynamicResource`.
- **Check:** The XAML has no `x:Class`, no event attributes, no `MergedDictionaries`, and no extension-assembly types.
- **Why:** Plans that relied on code-behind had to be redesigned.

### 5. Disable horizontal scrolling around wrapped text in lists

- **Rule:** For a `ListBox` or `ItemsControl` with wrapping `TextBlock` items, set `ScrollViewer.HorizontalScrollBarVisibility="Disabled"`, and consider `ScrollViewer.CanContentScroll="False"` for tall items.
- **Check:** A screenshot after a long response shows the full text and that the list scrolls to the end.
- **Why:** With horizontal scrolling on Auto, items were measured with infinite width, and long responses were cut off and could not be scrolled fully.

### 6. Use a selector for settings with a finite set of values

- **Rule:** When a setting accepts a known set of values (language, mode, tier), bind it to a `ComboBox` over that set, with a display name per value. Do not use free text.
- **Check:** The settings UI lists every supported value.
- **Why:** A free-text language field accepting `auto`, `ja`, or `en` was unclear to the user and was replaced by a selector.

### 7. Verify in the Experimental instance, including visual states

- **Rule:** After a Remote UI change, run the extension in the Experimental instance and check enabled and disabled states, selection and focus colors, a narrow tool window, theme or high contrast, and the language setting when localization changed.
- **Check:** The report includes screenshots and a pass or fail per state. If the user verified it, record who verified it and how.
- **Why:** A stop button that looked disabled, a selection that rendered white, truncated account information in a narrow window, and an untranslated UI were found only in the real IDE after the build and tests passed.

## Done checklist

- [ ] Every bound member has `[DataMember]`.
- [ ] Bound collections are diff-merged and reordered with `Move`.
- [ ] Selector `null` write-back is ignored only while the selection is valid.
- [ ] XAML has no code-behind, events, merged dictionaries, or custom controls.
- [ ] Wrapped text in lists has horizontal scrolling disabled.
- [ ] Finite settings use selectors.
- [ ] Experimental-instance screenshots cover states, colors, width, and language.
