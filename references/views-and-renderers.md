# Views and renderers

A view is a two-part thing: a **contribution** (`[[contributes.views]]`, which the
host renders into a container) and a **model** (`ViewInstance`, which the plugin
fills). The contribution decides the renderer; the model decides the content.

**Contents**: [Identity](#identity) · [API](#api) · [Placements](#placements) ·
[Ordering](#ordering-open-then-snapshot) · [Patch protocol](#patch-protocol) ·
[Component events](#component-events) · [Routing](#routing) ·
[Typed renderer views](#typed-renderer-views) · [Multi-instance](#multi-instance-and-lifecycle)

```
manifest: view id "acme.tools.main", container "acme.tools", renderer "native.form"
host:     mounts instance "container:acme.tools"
plugin:   views.create("acme.tools.main") -> ViewInstance(view_id, instance_id)
```

## Identity

| Name | Who assigns it | Lifetime | Notes |
| --- | --- | --- | --- |
| `view_id` | you, in the manifest | forever | Contribution id, must start with `<plugin id>.` |
| `instance_id` | host, or derived | one mount | `container:<containerId>` for sidebar, `tab:<n>` for tabs |
| `tab_id` | host | one tab | Present on tab placements; use it for `editor_tabs` / `focus` |

`views.create(view_id, instance_id=None)` derives the sidebar instance id by
reading `contributes.views` from `plugin.toml` (via `PYRITE_IDE_PLUGIN_DIR`). Pass
`instance_id` only when you are mounting into a host-allocated tab.

## API

```python
views.create(view_id, instance_id=None, *, placement="sidebar",
             tab_id=None, session_id=None) -> ViewInstance

views.open(view_id, *, placement="sidebar", title=None, callback=None)
    -> ViewInstance | None      # sidebar returns it, tab placements call back

views.get(instance_id, view_id=None) -> ViewInstance | None
views.resync_all() -> None      # re-send every snapshot (after reconnect)
views.dispose_all() -> None     # called by the SDK on dispose
```

`ViewInstance` (extends `ViewModel`):

```python
instance.view_id, instance.instance_id, instance.placement, instance.tab_id
instance.open(callback=None)
instance.close(callback=None)     # closes the tab when it has one
instance.focus(callback=None)
instance.snapshot(nodes, revision=None, callback=None)
instance.insert(id, data, index=None)
instance.update(id, data)
instance.remove(id)
instance.move(id, index)
instance.batch()                  # context manager
instance.flush() -> bool
instance.resync()
instance.on_event(component_id, event, handler)
instance.off_event(component_id, event)
instance.invoke_component(component_id, method, arguments=None, callback=None)
instance.on_visibility(handler)   # handler(visible: bool)
instance.visible
instance.on_route(handler)        # handler(route, params)
instance.push_route(route, params=None, callback=None)
instance.replace_route(...) / instance.goto_route(...) / instance.pop_route(...)
instance.route / route_stack / route_params
```

### Placements

| Value | Result |
| --- | --- |
| `"sidebar"` | Mounted at `container:<containerId>`. `views.open` returns the instance synchronously. |
| `"editor"` | Tab in the editor area's active group |
| `"console"` | Tab in the docked console panel |
| `"focused"` | Tab in the pane the user last interacted with (host default) |
| `int` or decimal string | That editor split group, same index as `editor_tabs.list()` |
| `"expansion"` | Legacy flag; accepted and ignored. Prefer `"focused"` |

Every non-sidebar placement allocates an instance id on the host, so
`views.open` returns `None` and delivers the instance later:

```python
def _open_tab(self):
    def _created(instance=None, error=None, **_):
        if error is not None:
            self.message.error(str(error)); return
        instance.snapshot(self._tab_tree())      # render here, not after open()
    self.views.open("acme.tools.main", placement="console",
                    title="Acme", callback=_created)
```

Tab placements need `tab.create`; activating/closing them needs `tab.manage`.

## Ordering: open, then snapshot

`open()` tells the host to install a fresh (empty, loading) model. A snapshot sent
before that lands on a model the host then replaces — the classic "spinner
forever" bug.

```python
def on_start(self):
    self.main = self.views.create("acme.tools.main")
    self.main.open(callback=self._render)

def _render(self, **_):
    self.main.snapshot(self._tree())
```

The one safe exception: a snapshot taken in `__init__`, before `plugin.start()`,
is queued by the SDK (`push` returns `False`, `_needs_snapshot` is set) and
`open()` re-sends it. Do not rely on that after start.

`snapshot()` always resets patch state: revision becomes 1 (or the `revision` you
pass), pending ops are dropped, and the handler table is rebuilt from the tree — so
handlers for removed nodes disappear automatically.

## Patch protocol

After the first snapshot, mutate incrementally:

```python
with self.main.batch():
    self.main.update("acme.status", {"props": {"id": "acme.status", "value": "3 files"}})
    self.main.insert("acme.row.3", ListTile(id="acme.row.3", title="new.py"), index=3)
    self.main.remove("acme.row.0")
    self.main.move("acme.row.2", 0)
```

- `insert(id, data, index=None)` appends when `index` is `None` or past the end.
- `update(id, data)` merges `data` into the node **one key deep**: `props` is
  replaced wholesale, not deep-merged, so include every prop you want to keep.
- `data` is a wire-shaped node: `{"type": ..., "props": {...}}` — the `id` is
  forced from the patch id, so a mismatched `props.id` is harmless.
- Limits: 20 000 nodes per view, 2 000 ops per patch, 2 MiB per frame. Overflow
  raises `ViewProtocolError` before anything is sent.
- One patch may be in flight; ops issued while waiting stay queued and are merged
  into the next patch. `flush()` returns `False` when nothing was sent.
- A rejected patch triggers `resync()` — a full snapshot at `revision + 1` — so
  both sides converge. You never handle the nack yourself.
- While the view is hidden, ops are applied to the local model only and
  `_needs_snapshot` is set; the next visibility change re-sends a snapshot. Keep
  the local model correct and you do not need to special-case visibility.

The host echoes `ide.view.ack` / `nack` / `resync` / `route.sync` /
`visibility.changed` frames; `Views.handle_frame` routes them to the right
instance. This is automatic — do not call `ack`/`nack` yourself.

## Component events

When a component event fires, the host sends `ide.view.event` with `componentId`
and `event`. The SDK looks the handler up in the table collected from the current
tree and calls it with the payload dict. Consequences:

- Handlers must be attached to a node that is in the tree you last sent.
- Handlers are sync; returning a coroutine does nothing.
- `on_context_menu` is the one provider that may return an awaitable; the bridge
  awaits it and sends the resulting `ContextMenu` node back.

`ViewModel.on_event(component_id, event, handler)` registers a handler outside the
tree — required for renderer views, whose "components" are the view root itself.

## Routing

Routes are host-owned. The plugin asks; the host applies and syncs back.

```python
self.main.push_route("detail", {"id": "a.py"})
self.main.on_route(lambda route, params: self._render_route(route, params))
```

`route`, `route_stack`, and `route_params` mirror the last sync — do not treat them
as authoritative while a push is in flight. `sdk.view.route.*` requires
`ui.navigate`.

## Typed renderer views

For the eight native renderers, `views` exposes facades that produce typed data
nodes instead of a component tree. **The facade must match the manifest renderer**;
the host renders according to the manifest, not the facade. The one general-purpose
renderer is `native.form`: it accepts either a normal component tree (what a
`UiPlugin` snapshots) or `FormField` nodes through `views.form(...)`, which is why
the scaffolded template pairs `renderer = "native.form"` with a `Text` component.

```python
def on_start(self):
    self.outline = self.views.outline(
        "acme.tools.outline", title="Outline",
        actions=[ViewAction(id="acme.refresh", label="Refresh",
                            icon=Icons.refresh, on_trigger=lambda _e: self._reload())],
    )
    self.outline.on_select(lambda item: self._reveal(item.id))
    self.outline.on_activate(lambda item: self._open(item.id))
    self.outline.open(callback=lambda **_: self._reload())

def _reload(self):
    self.outline.set_items([
        OutlineItem(id="f", label="main.py", kind=12, line=0, has_children=True),
        OutlineItem(id="f.fn", label="run()", parent_id="f", line=12, detail="def run"),
    ])
```

| Facade | Renderer | Node classes |
| --- | --- | --- |
| `views.outline(view_id, instance_id=None, *, title, actions)` | `native.outline` | `OutlineItem` |
| `views.tree(..., expanded_ids, selected_id, indent, searchable, empty_label)` | `native.tree` | `TreeItem` |
| `views.virtual_list(..., item_count, item_height, selected_id, empty_label)` | `native.virtualList` | `VirtualListItem` |
| `views.table(..., columns, row_count, row_height, show_header, selected_id, sort_column, sort_ascending, empty_label)` | `native.table` | `TableColumn`, `TableRowItem` |
| `views.form(..., title, actions)` | `native.form` | `FormField` or a component tree |
| `views.markdown(..., title, actions)` | `native.markdown` | `MarkdownContent` via `set_markdown()` |
| `views.log(..., item_height, empty_label)` | `native.log` | `LogEntry` |
| `views.variable_inspector(..., title, actions)` | `native.variableInspector` | `VariableEntry`, `VariableScope`, `LoadMoreEntry` |

Shared facade API (`RendererView`):

```python
view.open(callback=None); view.close(callback=None)
view.set_items(items)          # diffed into snapshot/patch automatically
view.set_props(**props)        # merged into the reserved "__view_config__" node
view.set_actions(actions)
view.show_placeholder(label, state="empty", icon=Icons.info_outline, icon_color=None)
view.on_select(handler) / on_activate(handler) / on_request_children(handler)
view.on_context_menu(handler)  # -> ContextMenu component (or None / awaitable)
view.on_visibility(handler)
view.items; view.nodes; view.view_id; view.instance_id; view.visible
```

`set_items` requires every item to be a `NativeViewNode` (`TypeError` otherwise)
and performs a real diff: removals in reverse order, inserts at the new index,
moves when the order changed, updates when the node content changed — all inside
one `batch()`. Reuse node ids across refreshes and it stays cheap.

`show_placeholder` is sugar for `set_items([ViewPlaceholder(...)])`. `state` is a
free-form key that only shapes the node id (`state:<state>`), so any stable string
works; `"empty"`, `"loading"`, `"error"`, and `"unavailable"` are the conventional
ones, and the host decides which of them get special styling.

Renderer-specific extras:

- `TreeView.configure(expanded_ids, selected_id, indent, searchable, empty_label)`
- `VirtualListView.configure(item_count, item_height, selected_id, empty_label)`
- `TableView.set_columns(columns)`, `.configure(row_count, row_height, show_header, selected_id, sort_column, sort_ascending, empty_label)`
- `MarkdownView.set_markdown(text)`, `.on_link_tap(handler)`
- `LogView.append(entry)`, `.extend(entries)`, `.clear()`, `.configure(item_height, empty_label)`

Node constructors:

```python
TreeItem(id, label, parent_id=None, icon=None, has_children=False,
         children_state=ChildrenState.loaded, **metadata)
VirtualListItem(id, label, icon=None, **metadata)
TableColumn(id, label, width=None, flex=None, frozen=None, sortable=None)
TableRowItem(id, cells, **metadata)
FormField(id, label, value=None, kind="text", options=None)
MarkdownContent(text, id="content")
LogEntry(id, message, level="info", timestamp=None)
OutlineItem(id, label, parent_id=None, icon=None, icon_color=None,
            has_children=False, children_state=ChildrenState.loaded,
            kind=None, detail=None, line=None, column=None)
VariableEntry(id, name, type_name="", value="", parent_id=None, icon=None,
              icon_color=None, has_children=False, children_state=ChildrenState.loaded)
VariableScope(id, name, error=None, has_children=False)
LoadMoreEntry(id, parent_id, progress, label="Load more...")
ViewPlaceholder(state, label, icon=Icons.info_outline, icon_color=None)
```

`ChildrenState`: `unloaded`, `loading`, `loaded`, `error`. `IconColor`: `primary`,
`secondary`, `tertiary`, `muted`, `error`. Renderer nodes require real
`MaterialIcon` values for `icon` (a plain string raises `TypeError`), unlike
component props which accept either.

Actions:

```python
ViewAction(id, label, icon, on_trigger)                 # AppBar button
ViewMenuAction(id, label, items, icon=Icons.more_vert, on_trigger)  # AppBar menu
```

The facade publishes actions, `set_props` values, and the context-menu provider as
reserved nodes (`__view_config__`, `__context_menu_provider__`, plus action ids).
Do not reuse those ids for your own data.

Lazy trees: set `has_children=True` and `children_state="unloaded"`, then answer
`on_request_children` by inserting child nodes with `parent_id` set and updating
the parent's `children_state` to `"loaded"`. Use `LoadMoreEntry` for paged
children.

## Multi-instance and lifecycle

A single view can be mounted many times (sidebar + several tabs). Each mount is a
separate `ViewInstance` with its own tree, revision, and handler table; plugin
state is shared because it lives in the plugin process.

```python
self._instances = []

def _open(self, placement):
    def _created(instance=None, error=None, **_):
        if error is not None: return
        self._instances.append(instance)
        instance.snapshot(self._tree(instance))
    self.views.open("acme.tools.main", placement=placement, callback=_created)

def _refresh_all(self):
    for instance in list(self._instances):
        if getattr(instance, "_closed", False):
            continue                     # the user may have closed the tab
        try:
            instance.snapshot(self._tree(instance))
        except ViewProtocolError:
            continue
```

The host closes tabs without telling the plugin, so treat `_closed` (set by
`close()`) and a `ViewProtocolError` on send as "this instance is gone" and drop
it from your list. `on_visibility` is the supported hook for "the user switched
away", which is where you pause polling or expensive rendering.
