---
name: dotnet-coding
description: 'Implementation rules for C# and .NET code, learned from review findings and regressions. Use while writing or changing C# that handles JSON-RPC or WebSocket connections and notification handlers, Channel-based queues, methods that return a Task from inside a using block, ObservableCollection or list updates during an async send, enum or option parsing, duplicate detection keys, optional versus null configuration values, validation before an upload or API write, file paths, CLI exit codes and result messages, or localhost/loopback connections.'
---

# .NET Coding

Each rule is a defect that shipped or reached review. Apply it while writing the code and add the test named in the check.

## When not to use

- Remote UI view models, `[DataMember]`, and XAML: `vs-extension-remote-ui`.
- State ownership and version gates: `dotnet-architecture-design`.
- NuGet package versions: `nuget-validate`.

## Rules

### 1. Never await a request on the same connection inside a notification handler

- **Rule:** A handler running on a connection's read loop must not send a request on that connection and await the response; queue the follow-up to another task or a channel. Keep the read loop alive: catch and log handler exceptions, including the handler's own `OperationCanceledException`.
- **Check:** A test sends a notification whose handler issues a request over a real pipe or socket and completes within the timeout.
- **Why:** A sign-in notification awaited an account read on the same JSON-RPC connection; the response sat behind the blocked parse loop until a 15-second timeout.

### 2. Process ordered notifications through one consumer

- **Rule:** Write notifications to a `Channel<T>` read by one consumer (`ReadAllAsync`), not a task per notification. The read loop must not block on the channel: use an unbounded channel, or a bounded one written with `TryWrite` and an explicit overflow policy (for example `DropOldest` for progress deltas, or fail the connection).
- **Check:** A test sends A, B, C and observes A, B, C; a test fills the queue and the read loop still parses responses.
- **Why:** Parallel handling reordered message deltas and turn completion and corrupted Busy/Ready transitions.

### 3. Await inside using; do not return the Task

- **Rule:** A method that creates a disposable (`using var stream = …`) and calls an async operation on it is `async` and awaits that operation. Returning the `Task` without awaiting disposes the resource before the I/O completes.
- **Check:** No non-async method returns a task that uses a local it disposes; a test with a delayed I/O double completes without `ObjectDisposedException`.
- **Why:** A block-upload method returned its task from inside `using`, so the stream was disposed while the upload was still running.

### 4. Apply async results to the original target

- **Rule:** Carry the target (and, when operations overlap, the operation ID) into success, failure, and notification handlers. Update the active view only when the target still matches, and keep caches for targets that are not selected current. After a successful send, remove only the items captured in the send snapshot, by reference or ID. A timer or continuation from an earlier attempt must not complete a later one.
- **Check:** Tests add an item while the send is pending, switch targets before the response arrives, and restart an operation before its previous timer fires.
- **Why:** Send cleanup deleted newly added attachments, a delayed result appeared in another view, a notification for an unselected project left its cache stale, and a previous sign-in's timer ended the retried sign-in.

### 5. Reject unknown enum and option values

- **Rule:** When `Enum.TryParse` fails or a string is outside the known set, throw or report a validation error; never fall back to a default. When displaying data from a peer, show an unknown item type as an explicit fallback that names the type.
- **Check:** A test passes an unknown value and expects the error, matching the XML documentation; a display test covers an unsupported item type.
- **Why:** An unknown `Mode` silently became `include` and produced a wrong plan.

### 6. Include every distinguishing field in uniqueness keys

- **Rule:** Duplicate-detection keys include every field that changes meaning (mode, type, scope), not only target and group.
- **Check:** The same target in include and exclude mode passes validation.
- **Why:** Keying on `Target|GroupId` rejected a valid include/exclude pair.

### 7. Keep omitted, null, and value distinct

- **Rule:** Preserve the contract's distinctions between omitted, explicit `null`, empty, and other values, using a presence flag when omission and `null` differ. When merging into an existing settings file, handle each shape it contains (arrays, metadata maps) and preserve data the merge does not own.
- **Check:** Round-trip tests cover each supported state; merge tests show existing metadata survives.
- **Why:** An explicit `null` meaning "any app" was treated as omitted, and a merge processed a metadata map as an array.

### 8. Validate everything before the first side effect

- **Rule:** Validate the whole request, including values needed only for the final result or report and properties that exist on one platform but not another, before the first upload, API write, or file change. Code that runs after a remote change succeeded must not be able to throw on input.
- **Check:** A test with a missing platform-specific value fails before the fake remote records any call.
- **Why:** A publish succeeded remotely and then threw while building its result, because the result required a property that one platform's manifest does not have.

### 9. Use Path APIs for paths

- **Rule:** Use `Path.GetFileName`, `Path.Combine`, and related APIs; never split on `\` or `/`.
- **Check:** A test runs the helper with both separators, or CI runs it on Windows and a non-Windows OS.
- **Why:** A naming helper split on a hard-coded separator and broke on another OS.

### 10. Make result messages agree with the exit code

- **Rule:** Derive the final message from the same counts that decide the exit code. When any item failed, print no success or dry-run-complete message.
- **Check:** A test with one failure asserts a non-zero exit code and a failure summary.
- **Why:** A CLI printed "Dry run: no changes were applied." even when items failed.

### 11. Try every loopback address

- **Rule:** When connecting to `localhost`, try each resolved loopback address (`::1` and `127.0.0.1`) until one connects.
- **Check:** A server listening only on IPv6 loopback is reachable.
- **Why:** A client that pinned IPv4 could not reach a server listening only on `::1`.

### 12. Parse every input shape the user named

- **Rule:** Test each requested input shape before implementing a parser or recognizer. For a parsing bug, keep the exact failing input, including markup and line boundaries; normalize only what recognition needs and preserve exclusions such as fenced code. Verify a binary or archive parser against the platform's own tool for the same file.
- **Check:** Tests cover each requested shape, the original failing input, and a similar input that must stay excluded.
- **Why:** A choice recognizer missed requested shapes, emphasis after a question mark hid a valid question, and an archive parser mishandled a compression format the native tool read correctly.

## Before reporting done

Confirm each applicable Check above, or state which test was not written and why.
