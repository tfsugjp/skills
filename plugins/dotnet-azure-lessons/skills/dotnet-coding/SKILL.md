---
name: dotnet-coding
description: 'Implementation rules for C# and .NET code, learned from review findings and regressions. Use while writing or changing C# that handles JSON-RPC or WebSocket connections and notification handlers, Channel-based queues, ObservableCollection or list updates during an async send, enum or option parsing, duplicate detection keys, optional versus null configuration values, file paths, CLI exit codes and result messages, or localhost/loopback connections. Not for Visual Studio Remote UI XAML or view-model binding (vs-extension-remote-ui) or PowerShell (powershell-scripting).'
---

# .NET Coding

Each rule is a defect that shipped or reached review at least once. Apply it while writing the code and add the test named in the check.

## When not to use

- Remote UI view models, `[DataMember]`, and XAML: use `vs-extension-remote-ui`.
- Architecture decisions (state ownership, version gates): use `dotnet-architecture-design`.
- NuGet package version choice: use `nuget-validate`.

## Rules

### 1. Never await a request on the same connection inside a notification handler

- **Rule:** A handler that runs on a connection's read loop must not send a request on that connection and await the response. Queue the follow-up work to another task or a channel. Keep the read loop alive: catch and log handler exceptions, including `OperationCanceledException` from the handler itself.
- **Check:** A test sends a notification whose handler issues a request over a real pipe or socket and completes within the timeout.
- **Why:** A sign-in notification awaited an account read on the same JSON-RPC connection; the response sat behind the blocked parse loop until the 15-second timeout.

### 2. Process ordered notifications through one consumer

- **Rule:** Write notifications to a `Channel<T>` and read them with one consumer (`ReadAllAsync`). Do not start a task per notification when order matters. The read loop must not block on the channel: use an unbounded channel, or a bounded one written with `TryWrite` and an explicit overflow policy (for example `BoundedChannelFullMode.DropOldest` for progress deltas, or fail the connection). The consumer follows rule 1 and never awaits a response on the same connection inline.
- **Check:** A test sends A, B, C and asserts the handler observed A, B, C; a test fills the queue and shows the read loop still parses responses.
- **Why:** Parallel handling reordered message deltas and turn completion.

### 3. Apply async results to the original target

- **Rule:** Carry the target and, when multiple operations can overlap, the operation ID into success, failure, and notification handlers. Apply results to the original target. Update the active view only when the target matches and the result still applies to that view. After a successful send, remove only the items captured in the send snapshot, by reference or ID.
- **Check:** Tests add an item while the send is pending and switch targets before a response or notification arrives. The new item remains, and a late success or failure affects only its original target.
- **Why:** Send cleanup deleted newly added attachments, and a delayed result appeared in a different view after selection changed.

### 4. Reject unknown enum and option values

- **Rule:** Parse modes and kinds strictly. When `Enum.TryParse` fails or a string is not in the known set, throw or report a validation error; do not fall back to a default.
- **Check:** A test passes an unknown value and expects the error. XML documentation that says malformed values throw matches the behavior.
- **Why:** An unknown `Mode` silently became `include`, contradicting the documented behavior and producing a wrong plan.

### 5. Include every distinguishing field in uniqueness keys

- **Rule:** Duplicate detection keys include every field that changes meaning, such as mode, type, or scope, not only the target and group.
- **Check:** A test with the same target in include and exclude mode passes validation.
- **Why:** Keying on `Target|GroupId` rejected a valid include/exclude pair as a duplicate.

### 6. Keep omitted, null, and value distinct

- **Rule:** Preserve the distinctions the contract makes between omitted fields, explicit `null`, empty strings, and other values. Use a presence flag or an equivalent representation when omission and explicit `null` differ. For settings merges, inspect an existing file for distinct shapes such as arrays and metadata maps and preserve metadata the merge does not own.
- **Check:** Round-trip tests cover the distinct states the contract supports and the serialized request matches the receiver's required fields. For a merge, check that existing metadata survives and update assertions about the complete key set when its expected contents change.
- **Why:** An explicit `null` meaning "any app" was treated as omitted, and a settings merge tried to process a metadata map as an array. Preserving that map also required updating an existing expected-key assertion.

### 7. Use Path APIs for paths

- **Rule:** Use `Path.GetFileName`, `Path.Combine`, and related APIs. Never split on `\` or `/`.
- **Check:** Tests run on Windows and Linux paths.
- **Why:** A naming helper split on a hard-coded separator and broke on another OS.

### 8. Make result messages agree with the exit code

- **Rule:** Derive the final message from the same counts that decide the exit code. When any item failed, do not print a success or dry-run-complete message.
- **Check:** A test with one failure asserts a non-zero exit code and a failure summary.
- **Why:** A CLI printed "Dry run: no changes were applied." even when items failed.

### 9. Try every loopback address

- **Rule:** When connecting to `localhost`, try each resolved loopback address (`::1` and `127.0.0.1`) until one connects. Do not pin the first IPv4 result.
- **Check:** A test with a server listening only on IPv6 loopback connects.
- **Why:** A client that preferred IPv4 could not reach a server that listened only on `::1`.

### 10. Parse every input shape the user named

- **Rule:** When adding a parser or recognizer, test each requested input shape before implementing. For a text parsing bug, keep the exact failing input, including markup and line boundaries. Normalize only the part needed for recognition and preserve exclusions such as fenced code.
- **Check:** The tests cover each requested shape and, for a bug fix, the original failing input and a similar input that must remain excluded.
- **Why:** A choice recognizer missed some requested message shapes, and inline emphasis after a question mark hid an otherwise valid question.

## Done checklist

- [ ] No notification handler awaits a request on its own connection; the read loop survives handler exceptions.
- [ ] Ordered streams use one consumer and have an order test.
- [ ] Async results stay with the original target, and post-send cleanup removes only the snapshot.
- [ ] Unknown enum values fail.
- [ ] Uniqueness keys include every distinguishing field.
- [ ] Distinct configuration values round-trip, and merges preserve metadata.
- [ ] Paths use `System.IO.Path`.
- [ ] Messages match exit codes.
- [ ] Loopback connections try IPv6 and IPv4.
- [ ] Requested parser shapes and applicable regression inputs and exclusions have tests.
