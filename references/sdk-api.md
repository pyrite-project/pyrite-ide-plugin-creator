# SDK API reference

Everything below mirrors `pyrite_sdk` 1.2 in the local checkout
(`src/pyrite_sdk/`). Signatures are written without the trailing
`callback=None` default; `→ callback(...)` documents what the callback receives.

**Contents**

1. [Conventions](#conventions) · [Plugin types](#what-each-plugin-type-exposes) · [Lifecycle](#lifecycle)
2. [path](#path--plugin-owned-directories) · [message / clipboard / dialog](#message-clipboard-dialog) · [resources](#resources--packaged-assets)
3. [commands](#commands) · [configuration](#configuration) · [events](#events--host-event-bus)
4. [documents](#documents--editor-documents) · [editor](#editor) · [file](#file--workspace-tree) · [board](#board--device-filesystem)
5. [serial](#serial) · [runtime](#runtime--device-inspection) · [persistence](#persistence--plugin-scoped-keyvalue)
6. [editor_tabs](#editor_tabs-ui-plugins-only) · [settings](#settings) · [env](#env--runtime-environment)
7. [Declarative contributions](#declarative-contributions-datacontribute-and-available-on-any-plugin) · [bridge](#bridge--only-when-you-need-the-plumbing)

## Conventions

```python
# request-style: returns None, answers later
self.editor.get_text(callback=self._on_text)
def _on_text(self, data=None, error=None, **_): ...

# fire-and-forget: no answer at all
self.file.open_file("/workspace/main.py")
```

- Raw namespaces (`editor`, `file`, `board`, `serial`, `settings`, `persistence`,
  `message`, `clipboard`, `dialog`, `theme`, `i18n`, `stubs`, `lsp`, `path.get`)
  answer with `callback(data=…)`. Some hosts put a dict there
  (`{"line": 3, "column": 8}`); some put a scalar (`True`).
- Typed helpers answer with a named key instead: `document=`, `session=`, `page=`,
  `tabs=`, `result=`, `selection=`, `info=`, `instance=`.
- Failures always arrive as `callback(error=<exception>)`; `error.code` carries the
  host code (`permission_denied`, `timeout`, `unavailable`, `stale_reference`,
  `key_not_found`, `invalid_request`, `internal_error`).
- Callbacks execute on the bridge event loop and are not awaited. See SKILL.md §3.

## What each plugin type exposes

| Attribute | UiPlugin | ServicePlugin | DataPlugin |
| --- | --- | --- | --- |
| `bridge`, `context`, `path`, `settings`, `message`, `clipboard`, `dialog`, `resources`, `events`, `commands`, `configuration` | ✓ | ✓ | ✓ |
| `file`, `board`, `editor`, `persistence`, `theme`, `i18n`, `stubs`, `lsp`, `documents`, `runtime`, `serial`, `env` | ✓ | ✓ | — |
| `views`, `editor_tabs` | ✓ | — | — |
| `theme`, `i18n`, `stubs`, `lsp` | ✓ | ✓ | ✓ |

## Lifecycle

```python
class BasePlugin:
    def __init__(self, queue_size: int = 50) -> None
    def start(self) -> None          # alias: run(); blocks in asyncio.run
    def on_pause(self) -> Any: ...
    def on_resume(self) -> Any: ...
    def on_dispose(self) -> Any: ...

class UiPlugin(BasePlugin):      # + views, editor_tabs, serial
    def on_start(self) -> Any: ...        # abstract

class ServicePlugin(BasePlugin): # headless, still has editor
    def on_start(self) -> Any: ...        # abstract

class DataPlugin(BasePlugin):
    def on_contribute(self) -> Any: ...   # abstract
    def run_once(self) -> None
```

- The host dispatches `start`, `pause`, `resume`, `dispose`. `install` and
  `uninstall` exist in `LifecycleHook` but are host-side only.
- Hooks may be `async def`; the bridge awaits them.
- After `on_dispose`, the SDK clears `events`, `commands`, and `views` for you.
  Stop your own threads and timers; do not dispose those three yourself.
- `DataPlugin.on_start` calls `on_contribute()` then `bridge.stop_when_idle()`, so
  `run_once()` is a complete one-shot program.
- `plugin.context` → `PluginContext(id, session_id, generation, plugin_dir,
  data_dir, cache_dir, temp_dir, capabilities)`. Paths are absolute and
  host-created.

## `path` — plugin-owned directories

```python
path.plugin() -> Path      # the installed package (read-only in spirit)
path.data()   -> Path      # persistent per-plugin data
path.cache()  -> Path      # disposable cache
path.temp()   -> Path      # scratch space
path.get(scope, callback)  # "plugin" | "data" | "cache" | "temp"
```

The four no-argument helpers resolve from the injected context, so they work
offline; `get()` asks the host.

## `message`, `clipboard`, `dialog`

```python
message.show(message, type="info", callback)   # type: info | success | warning | error
message.info / success / warning / error(message, callback)

clipboard.set_text(text, callback)

dialog.open_file(title=None, initial_directory=None, callback)   # → data: str path
dialog.open_files(title=None, initial_directory=None, callback)  # → data: list[str]
dialog.open_folder(title=None, initial_directory=None, callback)
```

Dialogs require `dialog.show`; messages require `ui.notify`.

## `resources` — packaged assets

```python
from pyrite_sdk.api.resources import PluginResource

logo: PluginResource = plugin.resources.asset("assets/logo.png")
uri = plugin.resources.uri("assets/logo.png")   # "plugin-resource:///assets/logo.png"
```

Only paths below `assets/`, forward slashes, no `..`, no absolute paths. `Image`
and `Video` builders reject anything that is not a `PluginResource`.

## `commands`

```python
commands.register(command_id: str, handler) -> None
commands.unregister(command_id) -> None
commands.dispose_all() -> None
```

The handler is invoked as `handler(args=<dict>, context=<dict>)`; `context`
usually carries `viewId` / `instanceId` when the command came from a view. Return
values (or awaited results) are sent back to the host as the command result.
Handlers may be `async def`. `command_id` must match a `[[contributes.commands]]`
entry, otherwise the host never calls it.

## `configuration`

```python
configuration.get(configuration_id, *, callback)      # → data: value
configuration.set(configuration_id, value, *, callback)
configuration.list(*, callback)                        # → data: [{"id", "value", ...}]
configuration.on_changed(handler, *, configuration_id=None) -> Subscription
```

`on_changed` subscribes to `configuration.changed` with `delivery="latest"` and
pre-filters by plugin id and (optionally) one configuration id. The handler
receives `{"id": "<plugin id>.<key>", "value": …}`.

## `events` — host event bus

```python
events.subscribe(topic, handler, *, filter=None, delivery=None,
                 debounce_ms=None, callback=None) -> Subscription
events.unsubscribe(subscription_id) -> None
events.dispose_all() -> None

class Subscription:
    id: str
    topic: str
    disposed: bool
    def dispose(self) -> None
```

- `delivery`: `"every"` (default host behaviour), `"latest"`, `"batch"`,
  `"debounce"`, `"throttle"`. `debounce_ms` sets the window for the last three.
- `filter` is a payload-key match map, e.g. `{"pluginId": "acme.tools"}`.
- Handlers may take zero arguments or one payload argument, and may be `async def`.
  Exceptions are caught and reported; they never break the loop.
- The subscription is registered locally *before* the host acknowledges, so events
  arriving early are still routed. If the host rejects it, it is dropped so you can
  retry.

Topics the SDK subscribes to through typed helpers (a raw `subscribe` with the same
string is equivalent):

| Topic | Payload |
| --- | --- |
| `editor.activeDocument.changed` | document info |
| `editor.document.opened` / `.changed` / `.saved` / `.closed` | document info |
| `editor.document.selection.changed` | selection |
| `configuration.changed` | `{"id", "value"}` |
| `runtime.session.created` / `.ended` / `.state.changed` | session |
| `runtime.program.started` / `.paused` / `.resumed` / `.finished` | session/program |
| `runtime.backend.restarted` | generation info |
| `runtime.variables.changed` | scope/change info |

Other topics exist in the host. Subscribing to one the host does not know can come
back as an error on the subscription callback, so probe rather than assume.

## `documents` — editor documents

```python
documents.get_active(callback)                        # → callback(document=Document|None)
documents.get(document_id, callback)                  # → callback(document=Document|None)
documents.symbols(document_id, callback)              # → callback(result=SymbolResult)
documents.get_selection(document_id=None, callback)   # → callback(selection=Selection|None)
documents.reveal(document_id, line, column=None, callback)

documents.on_active_changed(handler, **kw) -> Subscription
documents.on_opened / on_changed / on_saved / on_closed / on_selection_changed
```

```python
@dataclass
class Document:
    document_id: str
    file_path: str
    language_id: str | None
    revision: int | None
    is_active: bool
    line_count: int | None
    text: str | None        # may be None; fall back to editor.get_text()

@dataclass
class Selection:
    document_id: str
    start: int              # absolute offsets
    end: int
    cursor: Position | None

@dataclass
class SymbolResult:
    document_id: str
    revision: int | None
    stale: bool             # buffer changed between request and answer
    symbols: list[DocumentSymbol]
```

`symbols()` errors with code `unavailable` when no language service is running.
`DocumentSymbol` carries `name`, `kind`, `detail`, `children`, and the **raw LSP
node** in `.raw` — there is no line field, because the host forwards LSP results
unchanged. Positions live in the raw node, and the shape depends on whether the
server answered with hierarchical `DocumentSymbol` or flat `SymbolInformation`:

```python
def position(symbol: DocumentSymbol) -> tuple[int, int]:
    raw = symbol.raw
    rng = raw.get("selectionRange") or raw.get("range")
    if rng is None:                                  # SymbolInformation
        rng = (raw.get("location") or {}).get("range") or {}
    start = rng.get("start") or {}
    return int(start.get("line", 0)), int(start.get("character", 0))
```

Those numbers are LSP's: 0-based lines, UTF-16 code units for the column.
`documents.reveal()` passes `line`/`column` straight to the editor, so feed them
through unchanged; if the cursor lands one line off, your editor is 1-based and the
fix is `line + 1`, not a different API. `reveal` is gated on `editor.write`, not
`editor.read` — it moves the user's cursor and scrolls the view.

## `editor`

```python
# text
editor.get_text(callback)                       # → data: str
editor.set_text(text, callback)
editor.get_line_count(callback)                 # → data: int
editor.get_line_text(line, callback)            # → data: str
editor.get_selected_text(callback)              # → data: str
editor.insert_text(text, callback)              # at the cursor
editor.replace_range(start, end, text, callback)
editor.clear(callback)

# cursor & selection
editor.get_cursor_position(callback)            # → data: {"line", "column"}
editor.set_cursor_position(line, column, callback)
editor.get_selection(callback)                  # → data: {"start", "end"}
editor.set_selection(start, end, callback)
editor.select_all(callback)
editor.go_to_line(line, callback)

# clipboard, history, search
editor.copy / cut / paste / undo / redo(callback)
editor.can_undo / can_redo(callback)            # → data: bool
editor.find(word, match_case=False, whole_word=False, callback)
editor.find_regex(pattern, callback)
editor.clear_search(callback)

# tabs & decorations
editor.open_file(path, callback)
editor.set_ghost_text(text, line, column, persist=False, callback)
editor.clear_ghost_text(callback)
editor.scroll_to_line(line, callback)

# key capture (permission: editor.keys)
editor.capture_keys(keys, callback)
editor.release_keys(keys=None, callback)
editor.on_key(handler) -> Callable[[], None]    # returns an unsubscribe
editor.off_key(handler)
```

**Ghost text.** `text` may contain `\n`, so multi-line suggestions work.
`persist=False` lets the host drop the hint when the cursor moves or the buffer
stops matching, and lets `Tab` / `Right` accept it natively. `persist=True` keeps
it until `clear_ghost_text()` — only use it when you also capture the dismissing
keys.

**Key capture.** Capture only the keys you need, and only while you own them:

```python
def _show(self, suggestion, line, column):
    self.editor.set_ghost_text(suggestion, line, column)
    self._captured = True
    self.editor.capture_keys(("tab", "escape"))

def _on_key(self, event):            # KeyEvent, may be async
    if not self._captured:
        return False
    if event.key == "tab":
        self.editor.insert_text(self._ghost); self._dismiss(); return True
    if event.key == "escape":
        self._dismiss(); return True
    return False

def _dismiss(self):
    if self._captured:
        self._captured = False
        self.editor.release_keys(("tab", "escape"))
    self.editor.clear_ghost_text()
```

A captured key is **always** suppressed: if your handler returns `False` the
editor still will not perform its default action, so emulate the fallback
explicitly. Keys are lowercase logical labels — `"tab"`, `"escape"`, `"enter"`,
`"arrowDown"`, `"numpad1"` (`normalize_key_name` folds `"Arrow Down"` →
`"arrowDown"`).

```python
@dataclass(frozen=True)
class KeyEvent:
    key: str
    label: str
    character: str | None
    shift: bool; control: bool; alt: bool; meta: bool
    is_down: bool; is_repeat: bool
```

## `file` — workspace tree

```python
file.get_file_list(path, callback)          # → data: list of entries
file.get_root_dir(callback)                 # → data: root path
file.get_focus_file_node(callback)
file.get_focus_folder_node(callback)
file.is_file(path, callback)                # → data: bool
file.is_directory(path, callback)
file.exists(path, callback)
file.read_file(path, callback)              # → data: str
file.write_file(path, content, callback)
file.create_file(path, callback)
file.create_folder(path, callback)
file.copy_file(src, dst, callback)
file.move_file(src, dst, callback)
file.get_unique_name(name, is_folder=False, callback)
file.upload_file(local_path, board_path, callback)

file.open_file(path)                        # fire-and-forget
file.open_folder(path)
file.rename(path, new_name)
file.delete(path)
file.save_current_file()
file.save_current_file_as()
file.upload_selected_local_file_item()
```

## `board` — device filesystem

Same shape as `file`, with device semantics and a different name set:

```python
board.get_dir_list(path, callback)
board.get_root_dir(callback)
board.get_focus_file_node(callback)
board.get_focus_folder_node(callback)
board.is_file / is_directory / exists(path, callback)
board.read_file(path, callback)
board.write_file(path, content, callback)
board.get_corresponding_file_path(path, callback)
board.download_file(board_path, local_path, callback)

board.open_file(path)                       # fire-and-forget
board.rename(path, new_name)
board.delete_file(path)
board.delete_folder(path)
board.download_selected_board_item()
```

`get_corresponding_file_path` maps a device path to its workspace counterpart —
useful to decide whether a board file is a stale copy of an editor buffer.

## `serial`

```python
serial.list_ports(callback)                     # → data: list of ports
serial.get_status(callback)                     # → data: status object (port, connected, …)
serial.connect(port, callback)
serial.disconnect(callback)
serial.send(data: str | bytes | Sequence[int], callback)
serial.send_command(command: str, chunked=True, callback)
serial.read(timeout_ms=1000, max_bytes=None, callback)   # → data: bytes/text
serial.run_python(code, timeout_ms=20000, callback)
serial.hardware_reset(callback)
serial.set_baud_rate(value, callback)
serial.set_auto_reconnect(value, callback)
```

## `runtime` — device inspection

```python
runtime.sessions(callback)                                  # → callback(sessions=[RuntimeSession])
runtime.state(session_id=None, callback)                    # → callback(session=RuntimeSession|None)
runtime.scopes(session_id, callback)                        # → callback(scopes=[Scope])
runtime.variables(session_id, scope_id, start=0, count=0, callback)  # → callback(page=Page)
runtime.children(reference, start=0, count=0, callback)     # → callback(page=Page)
runtime.object_info(reference, callback)                    # → callback(info=ObjectInfo|None)

runtime.on_session_created / on_session_ended / on_session_state_changed
runtime.on_program_started / on_program_paused / on_program_resumed / on_program_finished
runtime.on_backend_restarted / on_variables_changed         # all -> Subscription
```

```python
@dataclass
class RuntimeSession:
    session_id: str
    generation: int
    capability: str = "available"    # or "unavailable"
    program_state: str = "idle"

@dataclass
class Variable:
    name: str; type: str; repr: str
    reference: str | None
    has_children: bool
    named_variables: int
    indexed_variables: int

@dataclass
class Page:
    items: list[Variable]
    total: int | None
    start: int
```

Errors are mapped to exceptions on `error`:
`StaleReferenceError` (`stale_reference`) when a reference belongs to a previous
generation after a device restart, and `RuntimeUnavailableError` (`unavailable`)
when the backend cannot inspect without interrupting the program. After
`on_backend_restarted`, throw away every cached reference and re-query.

## `persistence` — plugin-scoped key/value

```python
persistence.get(group, key, callback)          # → data: value
persistence.set(group, key, value, callback)
persistence.delete(group, key, callback)
persistence.list_groups(callback)              # → data: list[str]
persistence.list_keys(group, callback)         # → data: list[str]
persistence.clear(group, callback)
```

Values must be JSON-serializable. Group names are free-form; namespace them
(`"cache"`, `"state"`) rather than dumping everything into one group.

## `editor_tabs` (UI plugins only)

```python
editor_tabs.list(callback)               # → callback(tabs=[EditorTab])
editor_tabs.activate(tab_id, callback)
editor_tabs.close(tab_id, callback)
```

```python
@dataclass(frozen=True)
class EditorTab:
    tab_id: str
    index: int
    name: str | None
    kind: str                 # "plugin_view" for plugin tabs
    placement: str = "editor"
    resource: str | None
    plugin_id: str | None
    view_id: str | None
    view_instance_id: str | None

    @property
    def is_plugin_view(self) -> bool
```

`tab_id` is host-assigned and stable; `activate`/`close` raise `ValueError` on an
empty id.

## `settings`

Ungrouped access:

```python
settings.get(name, callback)
settings.set(name, value, callback)
settings.list(callback)
```

Grouped accessors follow a strict `get_<key>()` / `set_<key>(value)` pattern over a
dotted setting name. Groups and their keys:

| Group | Attribute | Keys |
| --- | --- | --- |
| Theme | `settings.theme` | `mode`, `style`, `color`, `active_plugin_theme_id`, `use_material_context_menu` |
| Editor | `settings.editor` | `font_family`, `font_size`, `word_wrap`, `line_number`, `chinese_to_unicode`, `enable_signal_detection`, `upload_confirm_style`, `confirm_shortcut`, `cancel_shortcut`, `code_folding`, `guide_lines`, `local_suggestions`, `keyboard_suggestions`, `use_space_as_tab`, `tab_size`, `gutter_divider` |
| LSP | `settings.lsp` | `enabled`, `type`, `websocket_path`, `stdio_executable`, `stdio_args`, `disable_warning`, `disable_error`, `semantic_highlighting`, `code_completion`, `hover_info`, `code_action`, `signature_help`, `document_color`, `document_highlight`, `code_folding`, `inlay_hint`, `go_to_definition`, `rename` |
| Serial | `settings.serial` | `default_baud_rate`, `auto_reconnect`, `repl_mode`, `file_transfer_mode`, `hardware_reset_strategy` |
| Terminal | `settings.terminal` | `font_family`, `font_size`, `line_height`, `ligatures`, `appearance`, `minimum_contrast`, `custom_foreground`, `custom_background` |
| MicroPython stubs | `settings.micropython_stubs` | `enabled`, `auto_detect_layers`, `layers`, `extra_paths` |

Example: `settings.editor.set_font_size(14.0)`, `settings.theme.get_mode(cb)`.
Mutating IDE settings requires `settings.write` and affects the user's environment —
do it only when the plugin's purpose is exactly that.

## `env` — runtime environment

```python
env.get(callback)             # → callback(data=snapshot); also returns the cached snapshot
env.on_change(handler)        # handler(snapshot)

env.os                  # "windows" | "macos" | "linux" | "android" | …
env.is_desktop_platform
env.layout_mode         # "mobile" (0-599px) | "tablet" (600-839px) | "desktop" (840px+)
env.width, env.height
env.locale              # UI language tag
env.theme_mode          # "dark" | "light"
```

Properties are `None` until the first `get()` / change event. Layout changes are
debounced by the host.

## Declarative contributions (`DataPlugin`, and available on any plugin)

```python
theme.contribute(name, data, callback)
theme.register_runtime(name, data, callback)
theme.revoke(name, callback)
theme.get(name, callback)
theme.list(callback)

i18n.contribute(locale, messages, callback)
i18n.register_runtime(locale, messages, callback)
i18n.revoke(locale, callback)
i18n.get(locale, callback)
i18n.list(callback)

stubs.contribute(provider_id, profiles, kind="micropython", version="",
                 aliases=None, metadata=None, callback=None)
stubs.register_runtime(provider_id, profiles, kind="micropython", version="",
                       aliases=None, metadata=None, callback=None)
stubs.revoke(provider_id, callback)
stubs.list(callback)
stubs.get(provider_id, callback)
stubs.resolve_layers(layers, callback)

lsp.contribute(server_id, configuration, match=None, label="",
               environment=None, scope="auto", callback=None)
lsp.register_runtime(server_id, configuration, match=None, label="",
                     environment=None, scope="runtime", callback=None)
lsp.revoke(server_id, callback)
lsp.list(callback)
lsp.get(server_id, callback)
```

`contribute` persists for the session's contribution registry; `register_runtime`
registers for the current runtime generation only. `revoke` removes either.

`lsp.contribute` validates before sending: `configuration["mode"]` must be
`"flat"` or `"sectioned"` (with `configuration["section"]` set), `match` must carry
a non-empty `executables` list, and `scope` must be `"auto"` or `"runtime"`.

```python
self.lsp.contribute(
    server_id="mylsp",
    match={"executables": ["mylsp"]},
    configuration={
        "mode": "sectioned",
        "section": "mylsp",
        "stubs_paths_key": "extraPaths",
        "python_executable_key": "pythonInterpreter",
        "type_checking_mode_key": "typeCheckingMode",
    },
    environment={"MYPYPATH": "{stubsPaths}"},
)
```

`I18nKey` / `fallback_messages()` in `pyrite_sdk.api.data` give the host's own key
set and Chinese fallbacks, which is a useful reference when naming your own keys.

## `bridge` — only when you need the plumbing

```python
bridge.push(envelope, client=None, on_error=None) -> bool
bridge.push_wait_response(envelope, callback=None, client=None) -> bool
bridge.request_path(scope, timeout=5.0) -> Path
bridge.report_error(message, *, traceback_text=None, source=None)
bridge.stop()
bridge.stop_when_idle()
bridge.running
```

Plugin code should never build `Envelope` objects; the namespaces above exist so
you do not have to. `report_error` is the sanctioned way to surface a caught
exception in the IDE's plugin log.
