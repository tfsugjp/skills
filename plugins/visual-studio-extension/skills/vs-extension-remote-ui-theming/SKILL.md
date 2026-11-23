---
name: vs-extension-remote-ui-theming
description: 'Theme Remote UI tool windows and dialogs of a VisualStudio.Extensibility extension: rely on automatic theming first, reference Visual Studio color tokens (ShellColors in Visual Studio 2026, legacy EnvironmentColors only for older targets) through DynamicResource, pair foreground and background per interaction state, re-base unthemed controls on VsResourceKeys styles, and keep selected-row text readable. Use for Remote UI XAML colors, styles, hover and selection states, and High Contrast; not for general WPF apps outside Visual Studio.'
---

# Remote UI Theming

Rules for making Remote UI XAML look native in every Visual Studio theme. Rules tagged **observed in practice** come from real rendering defects and are not documented on Microsoft Learn.

## When not to use

- Data contracts, bindings, collections, and XAML limits of Remote UI: use `vs-extension-remote-ui` (plugin `dotnet-azure-lessons`, if installed).
- WPF bindings, threading, virtualization, and accessibility in general: use `wpf-xaml` (plugin `wpf-xaml`, if installed).

## Rules

### 1. Let standard controls take the theme before adding colors

- **Rule:** Start from standard controls with no `Background`, `Foreground`, `FontFamily`, or `FontSize` set. Add explicit colors only for custom surfaces or for a control that is visibly unthemed in the Experimental Instance.
- **Check:** Every explicit color in the XAML is a theme resource key, and each one has a reason (custom surface or observed unthemed control).
- **Why:** Remote UI applies the Visual Studio theme to standard controls automatically, and hard-coded values break in other themes (Microsoft Learn).

### 2. Use the color tokens of the Visual Studio versions you support

- **Rule:** For Visual Studio 2026 and later, reference `ShellColors` keys (for example `ShellColors.ToolWindowTextBrushKey` and `ShellColors.ToolWindowBackgroundBrushKey`) and do not add new uses of the legacy `EnvironmentColors`, `CommonControlsColors`, or `TreeViewColors`. If the manifest's minimum version is older than Visual Studio 2026, confirm that every key resolves in the oldest supported version, or keep the legacy keys and record that choice. Take key names from the theme color token reference; never invent one.
- **Check:** Each color key exists in the reference for every supported Visual Studio version, and the window was viewed in each supported major version.
- **Why:** Visual Studio 2026 replaced the legacy color classes with semantic `ShellColors` tokens; refactored UI reads the new tokens first, so legacy keys can theme incompletely (Microsoft Learn).

### 3. Always use DynamicResource for theme keys

- **Rule:** Reference theme colors with `DynamicResource`, never `StaticResource` or an `x:Static` brush value, and assign Visual Studio styles to a control's `Style` property with `DynamicResource`. The one exception is `Style.BasedOn`, which is not a dependency property and must use `StaticResource` (for example `BasedOn="{StaticResource {x:Static styles:VsResourceKeys.ButtonStyleKey}}"`).
- **Check:** A search of the XAML finds no `StaticResource` that targets a theme color key, and `StaticResource` appears only in `BasedOn`.
- **Why:** Only `DynamicResource` re-resolves when the user switches theme or edits theme color tokens while the window is open (Microsoft Learn). `BasedOn` cannot take a `DynamicResource`, so the XAML fails to load if it is used there.

### 4. Pair foreground and background for every state

- **Rule:** Treat normal, hover, selected or pressed, disabled, and focused as foreground and background pairs taken from the same token family. Whenever a trigger changes a background, the same trigger sets the matching foreground.
- **Check:** A structural test of the XAML asserts that each background setter in a trigger has a matching foreground setter.
- **Why:** Observed in practice: changing only the background produced white-on-white and black-on-black text in some themes.

### 5. Re-base unthemed controls on Visual Studio styles

- **Rule:** When a control renders with default WPF colors inside a themed window, give it a style `BasedOn` the matching `VsResourceKeys` style (for example `TextBoxStyleKey` or `ButtonStyleKey`). For `ListBoxItem` selection and hover, use a template whose triggers set paired theme keys. Do not add an implicit `TextBlock` style that sets `Foreground`.
- **Check:** The window shows no default blue selection or white control in the Dark theme, and no implicit `TextBlock` style sets `Foreground`.
- **Why:** Observed in practice: a themed container did not theme child `ListBox`, `TextBox`, and `Button` templates. An implicit `TextBlock` `Foreground` setter overrides inherited foreground, so it broke the text of selected rows.

### 6. Keep text inside selected rows readable

- **Rule:** For selectable rows that contain buttons or other controls:
  1. Keep the row's background and foreground triggers paired (rule 4).
  2. Set the button's normal foreground to a theme key explicitly.
  3. Bind the button foreground to the ancestor row's foreground, or add `DataTrigger`s bound through `RelativeSource` to the ancestor row's `IsMouseOver` and `IsSelected`.
  4. Do not let child text install a competing foreground setter. Use `Style="{x:Null}"` only as a narrowly scoped last resort, and retest focus, High Contrast, and accessibility afterwards.
- **Check:** Hover, mouse selection, and keyboard selection each show readable button text in Dark, Light, and High Contrast.
- **Why:** Observed in practice: a `Button` style's default foreground took precedence over the selected row's foreground and made the text unreadable.

### 7. Do not reduce the opacity of essential text, and keep focus visuals

- **Rule:** Do not use `Opacity` to dim essential text; use a secondary text token instead. Keep the Visual Studio focus visual, and use Visual Studio styles or tokens for disabled, focused-selected, and unfocused-selected states instead of invented fallback colors.
- **Check:** High Contrast shows all essential text at full contrast and a visible keyboard focus indicator.
- **Why:** Reduced opacity defeats High Contrast colors.

### 8. Declare Visual Studio namespaces without adding a dependency

- **Rule:** Declare the `Microsoft.VisualStudio.Shell` and `Microsoft.VisualStudio.PlatformUI` XML namespaces with the assemblies that define the keys you use. `VsResourceKeys` and the legacy color classes are in `Microsoft.VisualStudio.Shell.15.0`. `ShellColors` is in the `Microsoft.VisualStudio.Shell` namespace; take its assembly name from the Microsoft Learn theming page or the VSExtensibility samples for your target Visual Studio version instead of guessing it. Do not add those assemblies as package references (see `vs-extensibility-project`).
- **Check:** The XAML loads in the Experimental Instance, and the project has no Shell package reference.
- **Why:** Remote UI XAML is loaded in the Visual Studio process, which provides these assemblies (Microsoft Learn).

### 9. Verify themes in the real IDE, including a live switch

- **Rule:** Check normal, hover, selected, disabled, keyboard-selected, and mouse-selected states in Dark, Light, and High Contrast, plus one theme with customized color tokens. Switch theme while the window is open.
- **Check:** Screenshots or notes record each state and theme; states that could not be observed are listed as gaps.
- **Why:** Users can override individual theme tokens, so default themes alone do not prove the UI follows the theme (Microsoft Learn).
