---
name: pyrite-ide-plugin-creator
description: Build, extend, debug, and package PyriteIDE plugins in Python against pyrite-sdk 1.2. Use this skill whenever a task touches a PyriteIDE plugin, a .pyrix archive, plugin.toml Manifest v2, pyrite_sdk imports, the pyrsdk CLI, UiPlugin/ServicePlugin/DataPlugin, plugin views or native UI components, or any plugin-facing editor/file/board/serial/runtime/theme API — including requests phrased as product features ("add a sidebar panel to my editor", "show device variables while debugging", "ship a dark theme", "make Tab accept my completion") even when the SDK is never named. Also use it when reviewing or repairing an existing plugin's manifest, rendering, callbacks, permissions, or packaging.
---

# PyriteIDE Plugin Creator

A PyriteIDE plugin is a normal Python process that the IDE launches with a private
native bridge. The plugin owns its code; the host owns the window, the editor, the
file tree, and the device. `pyrite_sdk` is the only supported way to talk to it.

**Ground truth is the local SDK source**, not this document and not the online docs.
When anything below disagrees with the checkout, the checkout wins — read it:

```bash
SDK=~/project/pyrite-project/pyrite-sdk        # adjust to the real path
grep -n "def " $SDK/src/pyrite_sdk/api/editor/editor.py
sed -n '1,120p' $SDK/src/pyrite_sdk/models/manifest.py
```

Two things never to do: hand-roll the bridge (WebSocket/TCP/sockets/envelopes/
handshakes are host-internal and unsupported), and invent SDK symbols. If a name
is not in the local source, it does not exist.

## 1. Choose the plugin type first

The base class decides which namespaces exist at all, so pick before writing code.

| Manifest `type` | Base class | Gets | Use when |
| --- | --- | --- | --- |
| `ui` | `UiPlugin` | everything, incl. `views`, `editor_tabs`, `serial` | The plugin contributes a sidebar panel, tab, or any visible UI |
| `service` | `ServicePlugin` | `file`, `board`, `editor`, `documents`, `runtime`, `serial`, `persistence`, `theme`, `i18n`, `stubs`, `lsp`, `env` — **no `views`** | Headless background work: inline completion, watchers, formatters |
| `data` | `DataPlugin` | `theme`, `i18n`, `stubs`, `lsp` only | One-shot declarative contributions (themes, locales, type stubs) |

`ServicePlugin` deliberately still exposes `editor`: an inline (FIM) completion
provider drives the editor without owning a view.

A `ui` manifest **must** declare at least one navigation container, even if the
plugin only opens editor tabs. The container is what the sidebar entry hangs off.

## 2. Project shape and the entry contract

```
my-plugin/
├── plugin.toml          # Manifest v2 — required
├── __main__.py          # entry point — required, this exact name
├── requirements.txt     # read by `pyrsdk package -rf` and `pyrsdk test`
└── assets/              # only what the manifest references as assets/…
```

`__main__.py` is a hard contract: the packager refuses to build without it (or its
`.pyc`), and `pyrsdk test` looks for it by name.

Scaffold, then edit:

```bash
pyrsdk create ui acme-tools ./my-plugin     # writes my-plugin/src/{__main__.py,plugin.toml,requirements.txt}
pyrsdk create service acme-fim ./my-plugin
pyrsdk create data acme-theme ./my-plugin
```

`create` writes into `<dir>/src`, and the first positional argument becomes both
the manifest `id` and the contribution prefix. It only understands kebab-case
(`acme-tools` → class `AcmeToolsPlugin`). If you want a dotted id such as
`acme.tools`, scaffold with the kebab form and then rewrite `id`, `name`, and every
contribution prefix — passing `acme.tools` directly produces the invalid
`class Acme.toolsPlugin`.

Keep the module import-safe: build the plugin object at module level (that is what
the host imports), but only run the bridge under a main guard. Importing the module
outside the IDE raises `PluginContextError` because `BasePlugin.__init__` requires
the `PYRITE_IDE_PLUGIN_*` environment — that is expected, and it is why `pyrsdk
test` stubs the context instead of importing the file bare.

```python
plugin = AcmeToolsPlugin()

if __name__ == "__main__":
    plugin.start()          # blocking; DataPlugin uses plugin.run_once() instead
```

## 3. The callback contract — read this before writing a single call

Every request-style SDK method returns `None` immediately and answers later:

```python
self.editor.get_text(callback=self._on_text)
```

Five rules that prevent most plugin bugs:

1. **Accept a catch-all `**_`.** Raw calls deliver `callback(data=…)`; typed helpers
   deliver a named key (`document=`, `session=`, `page=`, `tabs=`, `instance=`,
   `result=`, `selection=`, `info=`). One signature covers both:

   ```python
   def _on_text(self, data=None, error=None, **_) -> None:
       if error is not None:
           self.message.error(str(error)); return
       ...
   ```

2. **Check `error` first.** Errors arrive as `callback(error=<exception>)` with the
   host's error code on `.code` (`permission_denied`, `timeout`, `unavailable`,
   `stale_reference`, …). There is no exception thrown at the call site.

3. **Callbacks run synchronously on the bridge event loop.** Anything slow —
   HTTP, disk, model inference — freezes every view, event, and command in the
   plugin. Move it to a worker thread. SDK calls made from other threads are
   marshalled back onto the loop for you (`call_soon_threadsafe`), so a worker can
   call `set_ghost_text`, `snapshot`, or `message.info` directly.

4. **Callbacks are not awaited.** An `async def` callback returns a coroutine that
   is never scheduled. Use a sync callback. (Event handlers, command handlers, and
   key handlers *are* awaited — those may be `async def`.)

5. **Fire-and-forget methods exist.** `file.open_file`, `file.delete`,
   `file.rename`, `file.save_current_file`, `board.open_file`, … take no callback
   and still require their permission.

To call a request-style method from a worker thread and block on the answer, use a
one-slot queue; never do this on the bridge loop:

```python
def call(self, func, **kwargs):
    box = queue.Queue(maxsize=1)
    func(callback=lambda **values: box.put_nowait(values), **kwargs)
    result = box.get(timeout=10)
    if result.get("error") is not None:
        raise RuntimeError(str(result["error"]))
    return result
```

## 4. Manifest v2 essentials

Full field-by-field spec: `references/manifest-v2.md`. The shape that actually
validates:

```toml
manifest_version = 2
id = "acme.tools"                  # ^[A-Za-z0-9][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)*$
name = "Acme Tools"
version = "1.0.0"
type = "ui"                        # ui | service | data
protocol_version = 1
python_version = "3.14"            # runtime the packager bundles: 3.12 | 3.13 | 3.14
author = "Acme"
description = "Outline and device helpers"
activation_events = ["onView:acme.tools.main", "onCommand:acme.tools.refresh"]
permissions = ["ui.view", "editor.read"]
platforms = ["windows", "linux", "macos", "android"]

[[contributes.navigation_containers]]
id = "acme.tools"                  # a container may use the bare plugin id
title = "Acme"
icon = { material = "extension_outlined" }
location = "primary"               # primary | secondary
order = 100

[[contributes.views]]
id = "acme.tools.main"             # every other contribution id needs the "<id>." prefix
container = "acme.tools"
title = "Acme Tools"
renderer = "native.form"           # see allowlist below
icon = { material = "handyman_outlined" }

[[contributes.commands]]
id = "acme.tools.refresh"
title = "Acme: Refresh"

[[contributes.menus]]
location = "commandPalette"        # view/title | view/context | navigation/context | commandPalette
command = "acme.tools.refresh"

[[contributes.configuration]]
id = "acme.tools.verbose"
title = "Verbose logging"
type = "boolean"                   # string | integer | number | boolean | array
default = false
```

Validation is strict and fails at install time, so run it locally first
(`scripts/verify_plugin.py`). The rules that bite most often:

- **Unknown keys are rejected.** `extra="forbid"` plus an explicit field allowlist —
  one typo (`permisions`, `render`, `activationEvents`) invalidates the manifest.
- **Ids are namespaced.** Contributions must start with `<plugin id>.`; duplicates
  are rejected case-insensitively; ids must contain a dot (the container is the one
  exception — it may be exactly the plugin id).
- **Renderers are an allowlist**: `native.tree`, `native.virtualList`,
  `native.table`, `native.form`, `native.markdown`, `native.log`, `native.outline`,
  `native.variableInspector`. `rfw` and `rfw.*` are rejected outright.
- **Permissions are an allowlist** and must be declared before the matching call
  works. Narrow read/write, never broaden to silence an error.
- **Icons**: exactly one of `{ material = "…" }` (must exist in the Material table,
  snake_case, e.g. `data_object`) or `{ asset = "assets/…" }` (file must exist and
  stay under `assets/`).
- **`python_version`** picks the bundled interpreter for packaging; omit it and you
  get 3.14. It is not the Python you develop with (the host needs ≥3.12).

`when` clauses are a tiny boolean language, evaluated against host context keys:

```
runtime.language == 'python' && (workspace.opened || device.connected)
```

Allowed keys: `editor.language`, `editor.hasDocument`, `runtime.language`,
`runtime.state`, `device.connected`, `workspace.opened`, `plugin.enabled`,
`view.active`. Allowed operators: `&& || ! == != ( )`, plus string/number/`true`/
`false` literals. Anything else is a manifest error.

## 5. Views: the order that actually renders

A view is a contributed slot (`[[contributes.views]]`) plus a model the plugin
renders into. The host mounts a sidebar view at the fixed instance id
`container:<containerId>`, and `views.create()` derives that id from the manifest
for you — so pass the view id and nothing else.

```python
def on_start(self) -> None:
    self.main = self.views.create("acme.tools.main")   # instance id = "container:acme.tools"
    self.main.open(callback=self._on_open)             # 1. ask the host to mount
    self.commands.register("acme.tools.refresh", self._refresh)

def _on_open(self, **_):
    self.main.snapshot(self._tree())                   # 2. only after the ack

def _tree(self):
    return [Scaffold(Column(Text("Ready")))]
```

The rule is *snapshot after the host acknowledges `open`*, not merely "call open
first". `open()` makes the host install a fresh loading model, and that install is
asynchronous: calling `open()` and then `snapshot()` in the same function still
loses the snapshot, and the view spins forever. Pass a callback and render inside
it.

The one safe exception: a snapshot taken in `__init__`, before `plugin.start()`, is
queued by the SDK (`push` returns `False`, `_needs_snapshot` is set) and `open()`
re-sends it. Do not rely on that after start.

Rendering rules:

- A snapshot is the full tree (`list[Component]`); afterwards use
  `insert(id, data, index)` / `update(id, data)` / `remove(id)` / `move(id, index)`,
  grouped with `with view.batch():` into one patch. Limits: 20 000 nodes, 2 000 ops
  per patch, 2 MiB per frame — exceed them and `ViewProtocolError` is raised.
- Every node that emits events, gets patched, or is driven by a controller needs a
  **stable unique `id`** in its props. Builders such as `Button`, `VirtualList`,
  `TreeView`, `DataTable`, `Canvas` mint a random id when you omit one, which
  breaks patching on the next render.
- Only one patch is in flight; operations issued while waiting are merged into the
  next one. You do not need to throttle.
- Patches while the view is hidden are applied locally and re-sent as a snapshot
  when it becomes visible, so `on_visibility` is for pausing expensive work, not
  for correctness.

Other placements (`views.open(view_id, placement=…)`) return `None` and deliver the
instance through `callback(instance=…, error=…)`. Placements: `"sidebar"`,
`"editor"`, `"console"`, `"focused"` (host default), an integer editor-group index,
or the legacy `"expansion"`.

Patch protocol, routing, visibility, and the typed renderer facades live in
`references/views-and-renderers.md`.

## 6. UI is a component tree

```python
from pyrite_sdk.api.components import Column, Row, Scaffold, Text, Button, Divider
from pyrite_sdk.api.icons import Icons
from pyrite_sdk.api.resources import PluginResource   # only for typing

def _tree(self):
    return [
        Scaffold(
            Column(
                Text("Acme Tools", style="heading"),
                Text("3 files changed", muted=True),
                Divider(),
                Row(
                    Button(id="acme.refresh", label="Refresh",
                           icon=Icons.refresh, variant="primary",
                           on_press=self._on_refresh),
                    Button(id="acme.clear", label="Clear", variant="ghost",
                           on_press=lambda _e: self.main.snapshot([])),
                    gap=8,
                ),
                gap=12,
            )
        )
    ]
```

- Builders return a `Component`, which is a plain dict
  (`{"type", "props", "children", "events"}`) — serializable by construction.
- Handlers receive the event payload dict (press, change, selection, …) and are
  **sync**. `Component.on(event, handler)` is the escape hatch for events a builder
  does not wrap.
- `Image` / `Video` require `self.resources.asset("assets/logo.png")`; a bare path
  raises `TypeError`.
- Icons come from `Icons.<snake_case_name>` (`Icons.data_object`,
  `Icons.extension_outlined`); the value is the wire token `material:<name>`.
- Imperative operations on a mounted component go through its controller:
  `field.controller.set_text("…")`, `list.controller.reveal_item(id)`,
  `canvas.controller.push_ops(ops)`.

Full catalog with every prop, event, data class, and Canvas op:
`references/ui-components.md`.

## 7. Host features, by namespace

| Namespace | Answers | Permission |
| --- | --- | --- |
| `views` | create/open/close view instances, patch, routes, visibility | — (the host treats view-model and route ops as private to your own view; UI plugins still declare `ui.view` as the umbrella) |
| `commands` | `register(id, handler)` for manifest commands | — |
| `configuration` | read/write the configuration this plugin declares, `on_changed` | — (scoped to your own ids) |
| `events` | subscribe to host topics with delivery modes | topic-dependent |
| `documents` | active document, symbols, selection, doc lifecycle events | `editor.read`; `documents.reveal` is `editor.write` |
| `editor` | text, cursor, selection, find, undo, ghost text, key capture | `editor.read` / `editor.write` / `editor.keys` |
| `file` / `board` | workspace tree and device filesystem | `file.read` / `file.write`, `board.read` / `board.write` |
| `serial` | ports, connect, send, read, run_python, reset | `serial.read` / `serial.write` |
| `runtime` | sessions, scopes, variables, lazy children | `runtime.inspect` |
| `persistence` | plugin-scoped key/value store | `persistence.read` / `persistence.write` |
| `editor_tabs` | list/activate/close host tabs | `tab.manage` (opening a tab placement also needs `tab.create`) |
| `settings` | IDE settings, grouped (`settings.editor`, `.theme`, `.lsp`, …) | `settings.read` / `settings.write` |
| `message` / `clipboard` / `dialog` | toasts, clipboard, native pickers | `ui.notify` / `ui.view` / `dialog.show` |
| `theme` / `i18n` / `stubs` / `lsp` | declarative contributions (`DataPlugin`) | `data.read` for `get`/`list`, `data.write` for `contribute`/`register_runtime`/`revoke` |
| `env` | os, layout mode, size, locale, theme mode + change events | — |
| `path` / `resources` | plugin/data/cache/temp dirs, `assets/` URIs | — |

Signatures, callback payloads, and event topics for every method:
`references/sdk-api.md`.

Two patterns are worth internalising because they are easy to get wrong:

**Configuration-driven plugin.** Defaults live in the manifest *and* in a local
dict; `configuration.list` returns `[{"id": "<plugin id>.<key>", "value": …}, …]`
with fully-qualified ids, and `configuration.changed` pushes `{"id", "value"}`.
Strip your own namespace prefix before comparing.

**Inline completion / key hijack.** `editor.set_ghost_text(text, line, column)`
shows multi-line ghost text and lets `Tab` accept it natively. Only call
`editor.capture_keys(("tab", "escape"))` while a suggestion is on screen, and
release them when it disappears: a captured key is *always* suppressed, so your
handler must emulate the fallback when it returns `False`. Requires `editor.keys`.

## 8. Verify, then package

Work outward from cheap checks to real ones:

```bash
pyrsdk test src                     # file presence + import under a stubbed bridge
python scripts/verify_plugin.py src # manifest validation + entry + symbol audit
pyrsdk package src -p Windows       # -> build/<plugin id>-Windows.pyrix (+ .hash)
pyrsdk package src -p all           # one archive per platform × architecture
```

`pyrsdk test <dir>` only checks that `__main__.py`, `plugin.toml`, and
`requirements.txt` exist and that the module imports with the bridge stubbed. It
does not validate the manifest, run `on_start`, or exercise any callback — a green
result is a syntax check, not a working plugin.

`pyrsdk package` reads `plugin.toml` from `<dir>`, installs `requirements.txt` for
the target platform/arch into a bundled `site-packages`, and writes
`build/<plugin id>-<Platform>[-<arch>].pyrix`. `-p all` expands to every platform in
`platforms` × every supported ABI (Android 3, Darwin 2, Windows 1, Linux 1 — seven
archives for the scaffold's four platforms), so a plugin ships one file per target
rather than one universal file.

`requirements.txt` is not optional bookkeeping: at runtime the host puts only
`<plugin>/site-packages`, `<plugin>/__pypackages__`, and the plugin directory on the
module path. `pyrite-sdk` itself therefore has to be a requirement (the scaffolded
`requirements.txt` points at a local wheel during development; a published plugin
pins the PyPI version), and any third-party import must be listed or it will fail on
the user's machine while working on yours.

Useful flags: `--arch`, `-rf/--requirements-file`, `-r/--requirements`, `--exclude`,
`--compile-app`, `--compile-packages`, `--skip-site-packages`, `--pip-tool uv|pip`,
`--asset`.

`pyrsdk` ships with the SDK package, so `pip install pyrite-sdk` (or a local wheel
built from the checkout) provides it. Users install the result through the IDE's
plugin page — ship each `.pyrix` together with its `.pyrix.hash`, which is what the
installer verifies.

Do not claim a plugin works because it packaged. Rendering, permissions, and host
callbacks are only exercised inside PyriteIDE — say so explicitly when you could
not run it there.

## 9. Failure modes worth recognising instantly

| Symptom | Cause | Fix |
| --- | --- | --- |
| Sidebar view spins forever | content sent before `open()`, or a custom `instance_id` that the host does not render | `open(callback=…)` then `snapshot(...)`; let `views.create` derive the id |
| View blank after a tab opens | `views.open` returns `None` for tab placements | render in `callback(instance=…)`, not on the return value |
| `TypeError: cb() got an unexpected keyword argument 'document'` | callback too narrow | add `**_` and read the typed key |
| Callback never fires | blocking the bridge loop, or an `async def` callback | move work to a thread; make the callback sync |
| `permission_denied` on a call that used to work | permission missing from `plugin.toml` | declare the narrowest permission that covers the call |
| Manifest rejected with `manifest_invalid_schema` | unknown key, wrong type, or bad contribution id | run `scripts/verify_plugin.py`; ids need the `<plugin id>.` prefix |
| `manifest_missing_navigation_container` | `type = "ui"` with no container | add `[[contributes.navigation_containers]]` |
| `stale_reference` from `runtime` | device restarted; references are generation-scoped | drop cached references, re-query `scopes`/`variables` |
| Component stops responding after a re-render | random ids from an omitted `id=` | give every interactive component a stable id |
| Command never appears in the palette | handler registered but no `[[contributes.commands]]` (and no menu entry) | `commands.register` only attaches a handler; declare the command and a `commandPalette` menu |
| Command does nothing before the view opens | `activation_events` lists only `onView:…` | add `onCommand:<command id>` |
| Toast silently missing | `message.show(type="warn")` (valid: `info`/`success`/`warning`/`error`) or no `ui.notify` permission | fix the type, declare `ui.notify` |
| `.pyrix` builds but the IDE rejects it | missing `__main__.py`, bad manifest, or wrong `platforms` | rebuild after `pyrsdk test` passes |

## Reference map

| File | Read it when |
| --- | --- |
| `references/manifest-v2.md` | authoring or debugging `plugin.toml`: every field, permission, renderer, `when` grammar, per-type examples |
| `references/sdk-api.md` | calling any namespace: exact signatures, callback payload keys, event topics |
| `references/ui-components.md` | building UI: full component catalog, props/events, controllers, Canvas ops, data classes |
| `references/views-and-renderers.md` | view lifecycle, patch protocol, placements, routing, typed renderer views |
| `references/recipes.md` | end-to-end patterns: sidebar tool, config-driven service, list/table paging, context menus, theme/i18n/stubs/LSP, persistence, runtime inspector |
| `scripts/verify_plugin.py` | before packaging or when a manifest is rejected |
