---
name: vs-extension-lifecycle
description: 'Make VisualStudio.Extensibility view models, tool windows, and worker processes shut down cleanly: idempotent and thread-safe Dispose, no explicit dispose of a RemoteUserControl data context, owned diagnostics readers, serialized worker start and stop, and one async-once cleanup task. Use for ObjectDisposedException or other exceptions when Visual Studio closes or debugging ends, and for code that starts or stops child processes from an extension.'
---

# VisualStudio.Extensibility Lifecycle and Shutdown

Rules for releasing resources owned by a Visual Studio extension. Rules tagged **observed in practice** come from real shutdown failures and are not documented on Microsoft Learn.

## When not to use

- General async lifetime and cancellation rules outside Visual Studio extensions: use `dotnet-coding` (plugin `dotnet-azure-lessons`, if installed).

## Rules

### 1. Make every disposable view model idempotent

- **Rule:** A view model that owns a `CancellationTokenSource` or other resources makes `Dispose` a no-op after the first call, using an `int` flag with `Interlocked.Exchange`:

  ```csharp
  private int disposed;

  public void Dispose()
  {
      if (Interlocked.Exchange(ref this.disposed, 1) != 0)
      {
          return;
      }

      this.lifetime.Cancel();
      this.lifetime.Dispose();
  }
  ```

- **Check:** A test calls `Dispose` twice, and concurrently from two threads, without an exception.
- **Why:** Observed in practice: `RemoteUserControl` disposes a data context that implements `IDisposable`, so an explicit `Dispose` in the control's override ran the view model's `Dispose` twice and threw `ObjectDisposedException` from `CancellationTokenSource.Cancel` when Visual Studio closed. Shutdown can call disposal from more than one thread, so a `bool` flag is not enough.

### 2. Do not dispose the data context yourself

- **Rule:** In a `RemoteUserControl` override of `Dispose(bool)`, release only resources the control owns. Leave the data context to the base class.
- **Check:** The override does not call `Dispose` on the data context.
- **Why:** Same failure as rule 1; idempotence is the safety net, not a reason to dispose twice.

### 3. Own every background reader you start

- **Rule:** Keep the cancellation source and `Task` of a redirected stdout or stderr reader as fields of the owning object. Do not fire and forget the reader, and do not defer process disposal into an unobserved `Task.Run`.
- **Check:** Every started reader task is awaited during shutdown.
- **Why:** Observed in practice: when debugging ended, the output channel and process disappeared while an unowned reader was still running, and the reader threw.

### 4. Serialize worker start and stop

- **Rule:** Guard worker process start, stop, and disposal with one async gate so that a concurrent connect, a failed start, and final disposal cannot split ownership or start a worker after disposal. A failed start runs the same core cleanup but does not mark the owner permanently disposed.
- **Check:** Tests cover disposal during connect, disposal after a failed start, and a retry after a failed start.
- **Why:** Without a gate, a start that races with disposal can split ownership or create a worker after the owner is disposed.

### 5. Shut down in a fixed order

- **Rule:** On shutdown: mark disposal, cancel diagnostics, dispose the RPC connection or pipe, terminate the worker and wait for it to exit, await the diagnostics reader, then dispose the cancellation source, the process, and any job object. Put the final releases in `finally`.
- **Check:** The shutdown method follows this order and a test asserts that no reader task is still running after disposal completes.
- **Why:** Disposing the process or cancellation source before the reader finishes raises exceptions in the reader.

### 6. Share one async-once cleanup task

- **Rule:** Represent cleanup as a single task that every `Dispose` and `DisposeAsync` entry point returns or observes. Start it directly from the view model so cancellation begins immediately. An async-capable host awaits it; a synchronous-only host keeps a reference and observes exceptions by logging them.
- **Check:** A test shows the cleanup body runs exactly once across `Dispose`, `DisposeAsync`, and repeated calls, and that a cleanup exception is logged rather than unobserved.
- **Why:** Scheduling the first cleanup call later postpones cancellation, and a cleanup task nobody holds can lose its exception.
