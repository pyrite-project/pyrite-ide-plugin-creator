# Recipes

Working patterns, ordered from "most plugins need this" to specialised. Every
snippet assumes the manifest pieces shown next to it — a contribution that is not
declared is invisible to the host no matter what the code does.

1. Sidebar tool with a command
2. Configuration-driven behaviour
3. Inline completion (ghost text + key capture)
4. Virtual list with paging
5. Tree with lazy children
6. Sortable table
7. Row context menu
8. Theme plugin
9. Localisation plugin
10. Language-server profile
11. Persistence across restarts
12. Device variables inspector
13. File ↔ board sync action
14. Multi-instance tabs
15. Package and verify

## 1. Sidebar tool with a command

**Manifest**

```toml
type = "ui"
activation_events = ["onView:acme.tools.main", "onCommand:acme.tools.refresh"]
permissions = ["ui.view", "file.read"]

[[contributes.navigation_containers]]
id = "acme.tools"
title = "Acme"

[[contributes.views]]
id = "acme.tools.main"
container = "acme.tools"
title = "Acme Tools"
renderer = "native.form"

[[contributes.commands]]
id = "acme.tools.refresh"
title = "Acme: Refresh"

[[contributes.menus]]
location = "commandPalette"
command = "acme.tools.refresh"
```

**Code**

```python
from pyrite_sdk.api.components import Button, Column, Divider, Scaffold, Text
from pyrite_sdk.core.plugin import UiPlugin

VIEW = "acme.tools.main"


class AcmeToolsPlugin(UiPlugin):
    def __init__(self) -> None:
        super().__init__()
        self._root: str | None = None
        self._files: list = []
        self._main = None

    def on_start(self) -> None:
        self.commands.register("acme.tools.refresh", self._on_command)
        self._main = self.views.create(VIEW)
        self._main.open(callback=self._render)
        self.file.get_root_dir(callback=self._on_root)

    def _on_root(self, data=None, error=None, **_):
        if error is not None or not data:
            self.message.warning("No workspace is open")
            return
        self._root = str(data)
        self._reload()

    def _on_command(self, args=None, context=None):
        self._reload()
        return {"ok": True}

    def _reload(self) -> None:
        if self._root is None:
            return

        def _on_list(data=None, error=None, **_):
            if error is not None:
                self.message.error(f"Could not list files: {error}")
                return
            self._files = list(data or [])
            self._render()

        self.file.get_file_list(self._root, callback=_on_list)

    def _render(self, **_) -> None:
        if self._main is None or getattr(self._main, "_closed", False):
            return
        self._main.snapshot([
            Scaffold(Column(
                Text("Acme Tools", style="heading"),
                Text(f"{len(self._files)} entries", muted=True),
                Divider(),
                Button(id="acme.refresh", label="Refresh",
                       on_press=lambda _e: self._reload()),
                gap=12,
            ))
        ])


plugin = AcmeToolsPlugin()

if __name__ == "__main__":
    plugin.start()
```

The root is resolved once and cached, because callbacks cannot return values: every
path-taking call needs it, and `get_file_list("")` is a host-side error rather than a
Python one.

## 2. Configuration-driven behaviour

**Manifest**

```toml
permissions = ["editor.read", "editor.write"]

[[contributes.configuration]]
id = "acme.fmt.enabled"
title = "保存时格式化"
type = "boolean"
default = true

[[contributes.configuration]]
id = "acme.fmt.max_lines"
title = "最大行数"
type = "integer"
default = 500
```

**Code**

```python
DEFAULTS = {"enabled": True, "max_lines": 500}
NS = "acme.fmt."

class FmtPlugin(ServicePlugin):
    def __init__(self) -> None:
        super().__init__()
        self._config = dict(DEFAULTS)

    def on_start(self) -> None:
        self.configuration.list(callback=self._on_config)
        self.configuration.on_changed(self._on_config_changed)
        self.documents.on_saved(self._on_saved, delivery="debounce", debounce_ms=150)

    def _on_config(self, data=None, error=None, **_):
        if error is not None:
            return                       # keep the manifest defaults
        for item in data or []:
            key = str(item.get("id", "")).removeprefix(NS)
            if key in self._config:
                self._config[key] = item.get("value")

    def _on_config_changed(self, event):
        key = str(event.get("id", "")).removeprefix(NS)
        if key in self._config:
            self._config[key] = event.get("value")

    def _on_saved(self, event=None):
        if not self._config["enabled"]:
            return
        ...
```

Defaults must exist in three places — the manifest, the local dict, and your
validation helpers — because the host may answer `configuration.list` after the
first event, or not at all if the user never touched a setting.

## 3. Inline completion: ghost text + key capture

**Manifest**

```toml
type = "service"
activation_events = ["onStartup"]
permissions = ["editor.read", "editor.write", "editor.keys"]
```

**Code (shape only — the request itself is your business)**

```python
import queue
import threading

from pyrite_sdk.core.plugin import ServicePlugin

CAPTURED = ("tab", "escape")


class CompletionPlugin(ServicePlugin):
    def __init__(self) -> None:
        super().__init__()
        self._ghost = None
        self._captured = False
        self._seq = 0
        self._lock = threading.RLock()

    def on_start(self) -> None:
        self.editor.on_key(self._on_key)
        self.documents.on_changed(
            self._on_changed, delivery="debounce", debounce_ms=350
        )
        self.documents.on_selection_changed(lambda _e: self._dismiss())

    # -- trigger ---------------------------------------------------------
    def _on_changed(self, event=None) -> None:
        self._dismiss()
        with self._lock:
            self._seq += 1
            seq = self._seq
        threading.Thread(target=self._work, args=(seq,), daemon=True).start()

    def _work(self, seq: int) -> None:
        context = self._read_context()          # uses a blocking call helper
        if context is None or not self._still_current(seq):
            return
        text = self._ask_model(context)         # network I/O — never on the loop
        if text and self._still_current(seq):
            self._show(text, context["line"], context["column"])

    def _still_current(self, seq: int) -> bool:
        with self._lock:
            return seq == self._seq

    # -- presentation ----------------------------------------------------
    def _show(self, text: str, line: int, column: int) -> None:
        self._ghost = text
        self.editor.set_ghost_text(text, line, column)     # persist=False
        self._captured = True
        self.editor.capture_keys(CAPTURED)

    def _dismiss(self) -> None:
        self._ghost = None
        if self._captured:
            self._captured = False
            self.editor.release_keys(CAPTURED)
        self.editor.clear_ghost_text()

    def _on_key(self, event):
        if not self._captured or not self._ghost:
            return False
        if event.key == "tab":
            self.editor.insert_text(self._ghost)
            self._dismiss()
            return True
        if event.key == "escape":
            self._dismiss()
            return True
        return False


plugin = CompletionPlugin()

if __name__ == "__main__":
    plugin.start()
```

Why this shape:

- The document event runs on the bridge loop; the model call must not.
- `debounce` collapses a burst of keystrokes into one trigger, which is cheaper
  than debouncing yourself.
- `_seq` invalidates stale answers: a slow response for an old cursor position must
  not paint over a newer one.
- Capture keys only while a suggestion is visible, and always release them in
  `_dismiss`, including on `on_dispose`.
- `persist=False` lets the host accept the hint on `Tab` by itself; the explicit
  capture is only needed if you want custom accept/dismiss semantics.

## 4. Virtual list with paging

```python
from pyrite_sdk.api.components import ListItem, VirtualList

PAGE = 200

def _list(self) -> VirtualList:
    return VirtualList(
        id="acme.list",
        items=[ListItem(id=row_id, label=label) for row_id, label in self._rows],
        item_count=self._total,
        on_select=lambda item: self._select(item.id),
        on_activate=lambda item: self._open(item.id),
        on_request_range=self._load_range,
    )

def _load_range(self, request) -> None:
    start, count = request.start, request.count or PAGE
    def _on_page(data=None, error=None, **_):
        if error is not None:
            return
        self._rows.extend(...)               # append the fetched slice
        self._view.update("acme.list", {"props": self._list()["props"]})
    self._fetch(start, count, callback=_on_page)
```

`item_count` is what makes the scrollbar honest; `on_request_range` is called with
the window the host is about to render, not with a page index. Rebuild the whole
`props` dict on update — `props` is replaced, not merged.

## 5. Tree with lazy children

```python
from pyrite_sdk.api.components import TreeNode, TreeView

def _tree(self) -> TreeView:
    return TreeView(
        id="acme.tree",
        nodes=self._nodes,
        expanded_ids=sorted(self._expanded),
        on_expand=lambda node: self._expanded.add(node.id),
        on_collapse=lambda node: self._expanded.discard(node.id),
        on_request_children=self._load_children,
    )

def _load_children(self, node) -> None:
    def _on_children(data=None, error=None, **_):
        if error is not None:
            return
        self._nodes.extend(
            TreeNode(id=child_id, label=label, parent_id=node.id, has_children=has_more)
            for child_id, label, has_more in data or []
        )
        self._view.update("acme.tree", {"props": self._tree()["props"]})
    self._fetch_children(node.id, callback=_on_children)
```

Mark a node `has_children=True` and leave its children out; the host asks once when
the user expands it. For very large trees use the renderer facade
(`views.tree`) with `TreeItem(children_state="unloaded")` plus `LoadMoreEntry`.

## 6. Sortable table

```python
from pyrite_sdk.api.components import DataTable, TableColumn, TableRow

def _table(self) -> DataTable:
    return DataTable(
        id="acme.table",
        columns=[
            TableColumn(id="name", label="Name", sortable=True, flex=2),
            TableColumn(id="size", label="Size", sortable=True, width=90),
        ],
        rows=[TableRow(id=r.id, cells={"name": r.name, "size": r.size}) for r in self._rows],
        sort_column=self._sort_column,
        sort_ascending=self._sort_asc,
        on_sort=self._on_sort,
        on_activate=lambda row: self._open(row.id),
    )

def _on_sort(self, column) -> None:
    if column.id == self._sort_column:
        self._sort_asc = not self._sort_asc
    else:
        self._sort_column, self._sort_asc = column.id, True
    self._rows.sort(key=..., reverse=not self._sort_asc)
    self._view.update("acme.table", {"props": self._table()["props"]})
```

Sorting is yours: the host reports the click, it does not reorder rows. Passing
`sort_column`/`sort_ascending` is what draws the arrow.

## 7. Row context menu

```python
from pyrite_sdk.api.components import ContextMenu, MenuItem, VirtualList

def _menu_for(self, item) -> ContextMenu:
    return ContextMenu(
        id="acme.row.menu",
        items=[
            MenuItem(id="open", label="Open"),
            MenuItem(id="rename", label="Rename"),
            MenuItem(id="delete", label="Delete", tone="danger"),
        ],
        on_select=lambda event: self._apply(event.item_id, item.id),
    )

VirtualList(
    id="acme.list",
    items=self._items,
    on_context_menu=self._menu_for,
)
```

The provider receives the row object (looked up by `targetId`) and must return a
`ContextMenu` component; returning `None` suppresses the menu for that row. The
menu's own handlers are registered when the host requests it, so they survive
without being part of the main tree.

## 8. Theme plugin

**Manifest**: `type = "data"`, `permissions = ["data.write"]`,
`activation_events = ["onStartup"]`.

```python
from pyrite_sdk.core.plugin import DataPlugin


class NordThemePlugin(DataPlugin):
    def on_contribute(self) -> None:
        self.theme.contribute("nord", {
            "mode": None,                       # None = both, or "light"/"dark"
            "color.primary": "#5E81AC",
            "color.onPrimary": "#ECEFF4",
            "color.surface": "#ECEFF4",
            "color.onSurface": "#2E3440",
            "dark.color.primary": "#88C0D0",
            "dark.color.onPrimary": "#2E3440",
            "dark.color.surface": "#2E3440",
            "dark.color.onSurface": "#ECEFF4",
        })


plugin = NordThemePlugin()

if __name__ == "__main__":
    plugin.run_once()
```

Keys are `color.*` and `dark.color.*` over the host's role names. `register_runtime`
is for themes that should vanish with the runtime generation; `revoke(name)` removes
one. Activate it with `settings.theme.set_active_plugin_theme_id("nord")` only if
the plugin is meant to switch the user's theme — otherwise let them choose.

## 9. Localisation plugin

```python
class ZhPlugin(DataPlugin):
    def on_contribute(self) -> None:
        self.i18n.contribute("zh_CN", {
            "acme.title": "工具",
            "acme.refresh": "刷新",
            "acme.empty": "暂无内容",
        })
```

`pyrite_sdk.api.data.I18nKey` lists the host's own keys with Chinese fallbacks —
useful when you need to align with existing UI wording. `i18n.register_runtime` is
the generation-scoped variant.

## 10. Language-server profile

```python
class MypyPlugin(DataPlugin):
    def on_contribute(self) -> None:
        self.lsp.contribute(
            server_id="mylsp",
            label="My LSP",
            match={"executables": ["mylsp", "mylsp.exe"]},
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

Validation is local: `mode` must be `flat` or `sectioned` (with `section`),
`match.executables` must be non-empty, `scope` must be `auto` or `runtime`.
`stubs.contribute(provider_id, profiles, kind="micropython", version="", aliases=[…])`
follows the same contribute/register/revoke rhythm; the `profiles` dicts are
host-defined, so read the shape from `stubs.list()` on a machine that already has a
stub provider rather than inventing keys.

## 11. Persistence across restarts

```python
def on_start(self) -> None:
    self.persistence.get("state", "last_file", callback=self._on_state)

def _on_state(self, data=None, error=None, **_):
    if error is None and data:
        self._last_file = str(data)

def _remember(self, path: str) -> None:
    self._last_file = path
    self.persistence.set("state", "last_file", path)
```

Values are JSON-serialisable. Use `data_dir()` from `path` for blobs and
`persistence` for small settings-like state; `cache_dir()` is disposable and
`temp_dir()` may be wiped between sessions.

## 12. Device variables inspector

```python
def on_start(self) -> None:
    self._session_id: str | None = None
    self._scope_of: dict[str, str] = {}      # node id -> scope id
    self.view = self.views.variable_inspector("acme.vars", title="Variables")
    self.view.on_activate(self._expand)
    self.view.on_request_children(self._expand)
    self.runtime.on_backend_restarted(lambda _e: self._reload())
    self.view.open(callback=lambda **_: self._reload())

def _reload(self) -> None:
    def _on_sessions(sessions=None, error=None, **_):
        if error is not None or not sessions:
            self.view.show_placeholder("No device session")
            return
        self._session_id = sessions[0].session_id
        self.runtime.scopes(self._session_id, callback=self._on_scopes)
    self.runtime.sessions(callback=_on_sessions)

def _on_scopes(self, scopes=None, error=None, **_):
    if error is not None:
        return
    items = []
    for scope in scopes or []:
        node_id = f"scope.{scope.id}"
        self._scope_of[node_id] = scope.id
        items.append(VariableScope(id=node_id, name=scope.name, has_children=True))
    self.view.set_items(items)

def _expand(self, node) -> None:
    scope_id = self._scope_of.get(node.id)
    if scope_id is None or self._session_id is None:
        return                                   # it is a variable, not a scope
    self.runtime.variables(
        self._session_id, scope_id, start=0, count=100, callback=self._on_page
    )

def _on_page(self, page=None, error=None, **_):
    if error is not None:
        return                       # StaleReferenceError / RuntimeUnavailableError
    self.view.set_items([
        VariableEntry(id=f"var.{v.name}", name=v.name,
                      type_name=v.type, value=v.repr,
                      has_children=v.has_children,
                      children_state="unloaded" if v.has_children else "loaded")
        for v in (page.items if page else [])
    ])
```

`StaleReferenceError` means the backend restarted: drop every cached reference and
start again from `sessions()`. `RuntimeUnavailableError` means inspection would have
to interrupt the running program — show a message instead of retrying. Page with
`start`/`count`; never ask for an unbounded scope.

## 13. File ↔ board sync action

```python
def upload_current(self) -> None:
    self.file.get_focus_file_node(callback=self._on_focus)

def _on_focus(self, data=None, error=None, **_):
    if error is not None or not data:
        return
    local = data if isinstance(data, str) else str(data.get("path", ""))
    if not local:
        return
    self._local_file = local
    self.board.get_root_dir(callback=self._on_root)

def _on_root(self, data=None, error=None, **_):
    if error is not None or not data:
        return
    name = self._local_file.replace("\\", "/").rsplit("/", 1)[-1]
    remote = f"{str(data).rstrip('/')}/{name}"

    def _on_read(text=None, error=None, **_):
        if error is not None:
            self.message.error(str(error)); return
        self.board.write_file(remote, str(text or ""), callback=self._on_written)

    self.file.read_file(self._local_file, callback=_on_read)

def _on_written(self, data=None, error=None, **_):
    if error is not None:
        self.message.error(str(error))
    else:
        self.message.success("Uploaded")
```

The reverse direction is `board.read_file(remote, callback=…)` followed by
`file.write_file(local, text, callback=…)`. `get_corresponding_file_path` maps one
tree to the other when the device mirrors the project, which is usually better than
string surgery on paths.

## 14. Multi-instance tabs

```python
def on_start(self) -> None:
    self.commands.register("acme.openConsole", self._open_console)
    self._instances = []

def _open_console(self, args=None, context=None):
    def _created(instance=None, error=None, **_):
        if error is not None:
            self.message.error(str(error)); return
        self._instances.append(instance)
        instance.snapshot(self._tree(instance))
    self.views.open("acme.tools.main", placement="console",
                    title="Acme Console", callback=_created)

def _tree(self, instance):
    return [Scaffold(Column(
        Text(f"instance {instance.instance_id}", muted=True),
        Text(f"tab {instance.tab_id}", muted=True),
    ))]
```

Same view id, many mounts. Each instance renders its own tree; shared state lives in
the plugin. Refresh all of them by iterating `self._instances` and skipping the
closed ones.

## 15. Package and verify

```bash
pyrsdk test src                        # file presence + import check
python scripts/verify_plugin.py src    # manifest validation, entry, symbols, ids
pyrsdk package src -p all              # one .pyrix per platform × architecture
```

Output is `build/<plugin id>-<Platform>[-<arch>].pyrix` plus a matching `.hash`.
Ship both; the hash is what the installer verifies. `requirements.txt` must list
`pyrite-sdk` (and every third-party import) because the host only adds the plugin's
own `site-packages` to the module path at runtime. If a build succeeds but the IDE
refuses the plugin, the manifest is almost always the reason — run the validator,
not the packager, to see why.
