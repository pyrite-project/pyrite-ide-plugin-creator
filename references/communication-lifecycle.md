# Communication and Lifecycle

PyriteSDK 1.x communicates with PyriteIDE through a host-injected native Dart bridge. Plugin code uses SDK namespaces and callbacks; it does not create a socket, choose a port, serialize protocol envelopes, or perform a handshake.

## Contents

- [Author-facing model](#author-facing-model)
- [Startup and handshake](#startup-and-handshake)
- [Plugin context](#plugin-context)
- [Plugin classes and available APIs](#plugin-classes-and-available-apis)
- [Lifecycle hooks](#lifecycle-hooks)
- [Callbacks and errors](#callbacks-and-errors)
- [Async commands and events](#async-commands-and-events)
- [Disposal](#disposal)
- [Output, queues, and long work](#output-queues-and-long-work)
- [Restart and recovery](#restart-and-recovery)
- [Diagnostic patterns](#diagnostic-patterns)

## Author-Facing Model

The communication path is:

```text
plugin method call
  -> PyriteSDK request
  -> host-injected native bridge
  -> PyriteIDE permission and API handler
  -> correlated response callback or subscribed event
```

Use this model when designing plugin state:

- An SDK request is asynchronous unless a method explicitly returns a local value.
- A callback belongs to one request and can complete out of order relative to other requests.
- An event subscription can deliver zero, one, or many events until disposed.
- A view event is routed by view instance, component ID, and event name.
- The host owns session identity, permissions, view mounting, and the authoritative route stack.
- In-memory state belongs to one plugin session and can disappear when the host restarts it.

Do not call private bridge queue methods in ordinary plugin code. Public APIs already add protocol identity, sequence numbers, request correlation, and error conversion.

## Startup and Handshake

`plugin.start()` and `plugin.run()` both enter the same blocking bridge loop. Call one of them once for a plugin instance. `DataPlugin.run_once()` enters that loop and requests shutdown after contributions and their pending callbacks settle; it is not an offline execution mode.

The protocol v1 startup sequence is host-managed:

1. PyriteIDE opens the native channel and sends initialization with plugin context.
2. PyriteSDK verifies the plugin ID, session, generation, directories, and protocol version.
3. PyriteSDK and PyriteIDE exchange initialized/ready frames.
4. The host sends lifecycle, command, event, view, and API frames only after ready.

This explains common startup failures, but plugin code must not reproduce these steps. A manually created TCP or WebSocket connection is not a supported plugin transport.

Entrypoint pattern:

```python
from pyrite_sdk.core.plugin import ServicePlugin


class IndexService(ServicePlugin):
    def on_start(self) -> None:
        print("Index service started")


def main() -> None:
    plugin = IndexService()
    plugin.start()


if __name__ == "__main__":
    main()
```

Keeping construction and `start()` in `main()` prevents ordinary imports from opening the bridge.

## Plugin Context

Read host-provided identity and directories from `plugin.context`. Treat the object as an immutable snapshot.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` / `plugin_id` | string | Manifest plugin ID. |
| `session_id` / `session` | string | Current plugin session identity. |
| `generation` | integer | Session generation used to reject stale frames. |
| `plugin_dir` | `pathlib.Path` | Installed plugin package directory. Read packaged files; do not use it for mutable data. |
| `data_dir` | `pathlib.Path` | Durable plugin-private data directory. |
| `cache_dir` | `pathlib.Path` | Re-creatable cached data. |
| `temp_dir` | `pathlib.Path` | Temporary session/work data. |
| `capabilities` | frozen set of strings | Capabilities announced by the host during startup. They are descriptive, not a substitute for manifest permissions. |

Prefer the convenience paths:

```python
data_file = plugin.path.data() / "index.json"
cache_file = plugin.path.cache() / "symbols.json"
temporary_file = plugin.path.temp() / "partial.bin"
```

Do not derive identity or storage locations from mutable process environment variables. Do not write into the installed plugin directory.

## Plugin Classes and Available APIs

All plugin classes expose:

- `bridge` as an implementation detail; do not build business logic on it.
- `context`
- `path`, `settings`, `message`, `clipboard`, `dialog`, `resources`
- `events`, `commands`, `configuration`

`UiPlugin` additionally exposes:

- `file`, `board`, `editor`, `persistence`, `serial`
- `documents`, `runtime`, `tabs`, `views`, `env`
- `theme`, `i18n`, `stubs`

`ServicePlugin` additionally exposes:

- `file`, `board`, `persistence`, `serial`
- `documents`, `runtime`, `env`
- `theme`, `i18n`, `stubs`

`DataPlugin` additionally exposes only the data contribution namespaces:

- `theme`, `i18n`, `stubs`

Choose a plugin class whose API surface matches its role. Do not assume `ServicePlugin` has `views`, `tabs`, or the direct `editor` namespace.

## Lifecycle Hooks

| Hook | Classes | Purpose |
| --- | --- | --- |
| `on_start()` | UI, Service | Register handlers/subscriptions, create initial models, and open or begin work. Required. |
| `on_contribute()` | Data | Register theme, localization, or stubs contributions. Required. May be sync or async. |
| `on_pause()` | all | Reduce optional work when the host pauses a session. Delivery depends on host lifecycle support. |
| `on_resume()` | all | Resume paused optional work. Delivery depends on host lifecycle support. |
| `on_dispose()` | all | Release timers, threads, handles, and plugin-owned external resources. |

Lifecycle hooks may be synchronous functions or `async def`. The bridge serializes lifecycle calls, so one hook does not run concurrently with another lifecycle hook for the same instance.

Keep `on_start()` responsive. Start background work and return instead of running an infinite loop on the bridge thread. Do not invent `on_install()` or `on_uninstall()` hooks; they are not part of the public plugin lifecycle.

Data lifecycle example:

```python
from pyrite_sdk.core.plugin import DataPlugin


class LocaleContribution(DataPlugin):
    def on_contribute(self) -> None:
        self.i18n.contribute(
            "en",
            {"acme.greeting": "Hello"},
            callback=self._on_contributed,
        )

    def _on_contributed(self, error=None, **response) -> None:
        if error is not None:
            print(f"Contribution failed: {error}")


def main() -> None:
    LocaleContribution().run_once()


if __name__ == "__main__":
    main()
```

`run_once()` waits for registered pending responses before stopping, but plugin logic should still handle response errors.

## Callbacks and Errors

The generic callback adapter behaves as follows:

- A successful object response is expanded into keyword arguments.
- A successful scalar/list response can arrive as the first positional value.
- A failed response calls the callback with `error=<exception>`.
- Some typed wrappers replace raw fields with named objects such as `document=`, `result=`, `sessions=`, `page=`, `info=`, or `instance=`.

Use tolerant signatures when an API is not a typed wrapper:

```python
def on_response(data=None, error=None, **fields):
    if error is not None:
        plugin.message.error(str(error))
        return
    value = fields.get("value", fields.get("path", data))
    print("Response:", value)


plugin.persistence.get("state", "last_file", callback=on_response)
```

For typed wrappers, use their documented keyword:

```python
def on_active_document(document=None, error=None):
    if error is not None:
        print("Cannot read active document:", error)
    elif document is not None:
        print(document.document_id, document.file_path, document.revision)


plugin.documents.get_active(callback=on_active_document)
```

There is no universal response timeout across SDK operations. For external workflows that must finish within a deadline, add plugin-level timing, cancellation state, and a user-visible fallback. Never spin-wait on the bridge thread.

Typical error categories include permission denied, missing resource/key, unavailable host capability, invalid request, stale runtime reference, view not mounted, transport closed, and queue full. Handle the error object rather than matching a rendered message string.

## Async Commands and Events

Commands declared in the manifest must be registered with the identical ID. A handler receives copies of `args` and `context` and may return a value or awaitable.

```python
async def refresh_command(*, args, context):
    force = bool(args.get("force", False))
    await refresh_index(force=force)
    return {"refreshed": True, "viewId": context.get("viewId")}


plugin.commands.register("acme.index.refresh", refresh_command)
```

Event subscriptions are session-owned:

```python
subscription = plugin.events.subscribe(
    "editor.document.changed",
    lambda event: print(event.get("documentId"), event.get("revision")),
    filter={"language": "python"},
    delivery="debounce",
    debounce_ms=100,
)

# Stop receiving this topic before session disposal when no longer needed.
subscription.dispose()
```

Delivery modes:

| Mode | Use |
| --- | --- |
| `every` | Deliver every event. Use only for low-rate topics. |
| `latest` | Coalesce a burst and deliver the latest value. |
| `batch` | Deliver events together over the configured window. |
| `debounce` | Deliver after activity settles. Useful for editor changes. |
| `throttle` | Limit delivery rate while activity continues. |

Handlers may be sync or async. One handler exception is reported and isolated; it does not stop the bridge or other subscriptions. A rejected subscription is removed locally so it can be corrected and registered again.

## Disposal

Write `on_dispose()` to be short, idempotent, and exception-free:

```python
class PollingService(ServicePlugin):
    def __init__(self) -> None:
        super().__init__()
        self._stop_requested = False
        self._subscription = None

    def on_start(self) -> None:
        self._subscription = self.events.subscribe(
            "runtime.session.state.changed",
            self._on_state,
            delivery="latest",
        )

    def on_dispose(self) -> None:
        self._stop_requested = True
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None

    def _on_state(self, event) -> None:
        if not self._stop_requested:
            print(event)
```

After normal disposal, the SDK clears commands, event subscriptions, and view registrations, and fails remaining callbacks with a transport-closed error. A disposed plugin instance cannot be restarted or reused.

Threads and external tasks are plugin-owned. Signal them to stop, close files/devices, and avoid callbacks that capture a disposed plugin indefinitely.

## Output, Queues, and Long Work

`stdout` and `stderr` are routed to the host while the plugin runs. Use normal `print()` for concise diagnostics, not high-rate telemetry.

The native receive queue and SDK send queue are bounded by the plugin's `queue_size` (default `50`). Queue overflow is a failure, not a retry mechanism. Reduce event volume with delivery modes, batch view changes, avoid printing inside tight loops, and move CPU/blocking I/O away from the bridge thread.

For long work:

- Snapshot the inputs required by the worker.
- Use a worker thread or async task appropriate to the library.
- Marshal SDK calls back through normal thread-safe public methods.
- Stop scheduling work after disposal.
- Present progress through bounded view patches or throttled messages.

## Restart and Recovery

PyriteIDE can restart a plugin or its runtime backend. Design for both:

- Plugin session restart: all Python in-memory state, callbacks, commands, subscriptions, views, and ephemeral Canvas overlays are lost. Rebuild them in `on_start()` and reload durable state from persistence/data storage.
- Runtime backend restart: runtime `reference` values from `Variable` and `ObjectInfo` are invalid. Listen for `runtime.backend.restarted`, re-query sessions/scopes, and rebuild the variable view.
- Hidden view: mutations are mirrored locally and the SDK sends a fresh snapshot when visibility returns. Keep stable IDs and do not create a separate hidden-state transport.
- Rejected view patch: the SDK requests/resends a full snapshot. Keep local model state authoritative enough to reconstruct it.

Never implement reconnect loops against the bridge channel. The host owns channel rebinding and starts a new plugin instance when required.

## Diagnostic Patterns

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Startup blocks forever in a test | `plugin.start()` ran during import or outside the host | Move startup behind the main guard; use `pyrsdk test` or mock public APIs. |
| Callback never updates local state | Code assumed a fixed `data` key or discarded `error` | Use a tolerant callback or the typed callback keyword. |
| Command is declared but not handled | Registration ID differs, registration occurs too late, or activation is missing | Match IDs exactly, register during `on_start`, and add `onCommand` when needed. |
| Events arrive too frequently | Delivery mode is `every` or no debounce window is set | Use `latest`, `debounce`, `batch`, or `throttle`. |
| Requests fail after disposal | A worker kept using the old instance | Stop workers and ignore late results after disposal. |
| Runtime child lookup reports stale reference | Backend generation changed | Discard references and query sessions/scopes again. |
| Bridge/queue error under load | Output, view patches, or events exceed bounded queues | Batch changes, throttle producers, and reduce logging. |
| A plugin tries to configure a port | It follows an obsolete transport model | Remove all socket/port code and call public SDK APIs only. |
