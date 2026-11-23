---
name: vs-extension-deployment
description: 'Deploy, package, and validate a VisualStudio.Extensibility extension: keep F5 under the SDK, avoid legacy VSSDK deployment properties, handle the LoaderLock MDA, clean up duplicate Experimental Instance identities with approval, validate the packaged VSIX, and compare build, package, and deployed assemblies. Use when F5 does not deploy or attach, the Experimental Instance runs old code, packaging fails or locks, or before calling an extension change verified.'
---

# VisualStudio.Extensibility Deployment and Validation

Rules for getting the right build into the Experimental Instance and the VSIX, and for proving it. Rules tagged **observed in practice** come from real failures and are not documented on Microsoft Learn.

## When not to use

- Build errors and project configuration: use `vs-extensibility-project`.
- Disposal and shutdown exceptions: use `vs-extension-lifecycle`.

## Rules

### 1. Let the SDK own F5

- **Rule:** In a pure out-of-process project, rely on the SDK's project capability for build, deployment, Experimental Instance launch, and debugger attachment. Do not add `DeployExtension`, `VSSDKTargetPlatformRegRootSuffix`, `CreateVsixContainer`, `StartAction`, `StartProgram`, or `StartArguments`.
- **Check:** The project file and launch profile contain none of these properties, and F5 deploys the current build and attaches the debugger.
- **Why:** Observed in practice: these VSSDK properties routed deployment into an incompatible folder layout or replaced the SDK launch with a plain `devenv` start that neither deployed nor attached.

### 2. Treat the LoaderLock MDA after F5 as debugger noise

- **Rule:** When the managed debugger attaches to `devenv.exe` and breaks on the `LoaderLock` managed debugging assistant, continue, or clear **Break When Thrown** for `LoaderLock` under **Debug > Windows > Exception Settings > Managed Debugging Assistants**. Do not change extension code for it.
- **Check:** The break occurs before any extension code runs and the stack shows only Visual Studio's native components.
- **Why:** Observed in practice: the MDA comes from Visual Studio's own mixed-mode components, not from the extension.

### 3. Suspect a duplicate identity before changing UI code

- **Rule:** When a command or tool window behaves like an older build while the built assembly is current, look for a second Experimental Instance deployment or hot-load entry before editing Remote UI code. Identify deployments by manifest identity, not by folder name.
- **Check:** Exactly one deployment carries the current identity, and no deployment carries a former identity.
- **Why:** Observed in practice: an earlier identity left behind after a rename kept contributing the same command with old behavior.

### 4. Clean up a former identity only with explicit approval

- **Rule:** Follow these steps in order:
  1. Close the Experimental Instance and its extension host processes.
  2. List the exact absolute deployment folders and registration entries for the former identity, and keep a recoverable backup.
  3. Get the user's approval for those exact targets before deleting anything.
  4. Remove only the former identity's deployment and registration entry; keep the current identity and every unrelated Experimental setting.
  5. Rebuild the configuration cache of the exact Visual Studio installation and root suffix that F5 uses, by running that installation's `devenv.exe /updateconfiguration /rootsuffix <suffix>`.
  A full Experimental Instance reset is a separate operation: it requires its own backup, re-confirmation of the exact installation and root suffix, and separate explicit approval. Approval for the targeted cleanup never covers a full reset.
- **Check:** After cleanup, a search finds zero former-identity entries and one current contribution, and the deployed assembly hash matches the build.
- **Why:** The Experimental Instance holds user settings and other extensions; deleting by folder name or resetting it removes data the user did not agree to lose.

### 5. Validate the VSIX the user will install, not the output folder

- **Rule:** Open the packaged `.vsix` and check its `extension.vsixmanifest`, the extension assembly, embedded Remote UI XAML resource names, `.vsextension` string resources, and every dependency that a side-loaded or in-process component needs beside it.
- **Check:** The verification report lists what was inspected inside the VSIX, not only `bin/`.
- **Why:** Observed in practice: a build output that looked complete still produced a VSIX without localized resources or a dependent assembly.

### 6. Run one deterministic end-to-end validation

- **Rule:** Validate from one build:
  1. Build the solution with warnings treated as errors.
  2. Run all tests with `--no-build` against that output.
  3. Inspect the VSIX manifest, assembly, and embedded XAML.
  4. Compare the hashes of the built, packaged, and Experimental-deployed extension assemblies.
  5. Confirm the command contribution is unique, then exercise keyboard, mouse, narrow width, theme, High Contrast, and high-DPI behavior.
- **Check:** The report shows one build, matching hashes, and the UI states that were observed; unobserved states are listed as gaps.
- **Why:** Rebuilding between steps can test one binary and ship another.

### 7. Use ActivityLog.xml for load failures

- **Rule:** When the extension does not load, read the Experimental Instance's `ActivityLog.xml` (start Visual Studio with `/log` when needed) before changing code.
- **Check:** The diagnosis quotes the relevant log entry.
- **Why:** Load failures usually leave no other visible error.

### 8. Stop only the exact process that locks the VSIX

- **Rule:** When packaging reports that the VSIX is locked, identify the `VsixUtil` process and command line that belong to this build before stopping it. Never stop other Visual Studio or packaging processes.
- **Check:** The stopped process's command line referenced this build's VSIX path.
- **Why:** Stopping by process name can kill the user's unrelated Visual Studio sessions.
