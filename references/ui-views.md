# Native Views

PyriteIDE plugin UI is hosted as contributed native views. A view instance receives either one free-form component tree or renderer-specific typed data. The SDK sends a full snapshot first and then revisioned patches.

Read `ui-components.md` for component constructors and `ui-examples.md` for complete implementations.

## Contents

- [Manifest, model, and instance](#manifest-model-and-instance)
- [Two rendering modes](#two-rendering-modes)
- [View lifecycle](#view-lifecycle)
- [Snapshots and patches](#snapshots-and-patches)
- [Visibility and recovery](#visibility-and-recovery)
- [Events and context menus](#events-and-context-menus)
- [View-local routes](#view-local-routes)
- [Typed renderer facades](#typed-renderer-facades)
- [Typed node reference](#typed-node-reference)
- [Renderer configuration](#renderer-configuration)
- [View actions and placeholders](#view-actions-and-placeholders)
- [Tab instances](#tab-instances)
- [Limits and invariants](#limits-and-invariants)
- [Selection guide](#selection-guide)

## Manifest, Model, and Instance

Three identities participate in a view:

| Identity | Source | Purpose |
| --- | --- | --- |
| View ID | `[[contributes.views]].id` | Stable view kind, for example `acme.tools.outline`. |
| Renderer | `[[contributes.views]].renderer` | Host-owned presentation for typed data, for example `native.outline`. |
| Instance ID | Sidebar default or host-created tab | Separates multiple mounted copies of the same view. |

For the contributed sidebar view, call `plugin.views.create(view_id)` or a typed facade without an explicit instance ID. The SDK associates it with the container placement declared by the manifest.

For a host-created tab, first call `plugin.tabs.create_view(...)`, receive a `TabViewInstance`, and create the model with its `instance_id`. Never assume the sidebar and tab share state merely because their view IDs match.

Every event, route, controller call, snapshot, and patch is scoped to one `(view_id, instance_id)` pair.

## Two Rendering Modes

### Component-tree mode

Send exactly one root `Component` as the snapshot node. The host detects the component's `type` and renders the complete nested tree. This is the mode for dashboards, forms, tool panels, media, menus, Canvas, and mixed layouts.

Recommended shapes:

- Direct root: `[Scaffold(...)]` or `[Column(...)]`.
- Patchable wrapper: `[{'id': 'root', 'component': Scaffold(...)}]`.

Use a single root. Multiple top-level components are interpreted as renderer data instead of one component tree. Wrap siblings in `Column`, `Row`, `Flex`, `Grid`, `Wrap`, `Tabs`, `Section`, or `Scaffold`.

Component trees have their own validation limits: maximum 5,000 component nodes and nesting depth 32. See `ui-components.md` for all 38 component contracts.

### Renderer-data mode

Use a typed facade such as `plugin.views.tree(...)` or `plugin.views.outline(...)`. Supply the corresponding typed node objects. The facade adds view configuration and actions, keeps stable IDs, computes insert/update/remove/move differences, and publishes patches.

Do not mix component nodes and renderer data in one view snapshot. A renderer-data view may expose context menus and title actions, but its row layout remains host-owned.

## View Lifecycle

`plugin.views.create(view_id, instance_id=None)` returns a `ViewModel`.

| Member | Effect |
| --- | --- |
| `open(callback=None)` | Ask the host to open/mount this instance. If an early snapshot was queued before the bridge became ready, `open` resends it. |
| `close(callback=None)` | Close the instance, clear queued patches, and make the model terminal. Later mutations raise `ViewProtocolError`. |
| `nodes` | Copy of the local ordered model. |
| `revision` | Local acknowledged/current revision. Starts at `0`; a first normal snapshot becomes `1`. |
| `has_in_flight` | Whether one patch is awaiting a response. |
| `pending_count` | Number of queued patch operations not yet sent. |

Create state and handlers before or during `on_start`, send an initial snapshot/items, then call `open()`. Calling `snapshot()` during `__init__` is supported because `open()` resends an undelivered early snapshot, but creating everything during `on_start()` is easier to reason about.

A typed `RendererView` exposes the same `open`, `close`, `visible`, and `on_visibility` behavior through its underlying `model`.

## Snapshots and Patches

### Full snapshot

`model.snapshot(nodes, revision=None, callback=None)` replaces the complete ordered model, clears pending/in-flight patches, rebuilds component handlers, and sends one authoritative revision.

Use a snapshot when:

- initializing a view;
- replacing a component tree wholesale;
- recovering from a session/view desynchronization;
- changing most rows at once;
- applying a hidden-view state when it becomes visible.

### Incremental operations

| Operation | Effect |
| --- | --- |
| `insert(id, data, index=None)` | Add a node with stable `id`; append when `index` is omitted/out of range. |
| `update(id, data)` | Merge changed fields into the matching node, preserving its ID. |
| `remove(id)` | Remove the matching node if present. |
| `move(id, index)` | Move the matching node to a new ordered index. |
| `flush()` | Send queued operations if no patch is in flight; returns whether one was sent. |
| `batch()` | Context manager that defers flush and emits grouped changes together. |
| `resync()` | Clear pending changes and resend the current local model as a new snapshot. |

Use `with model.batch():` when applying related mutations. Outside a batch, each mutation attempts to flush immediately.

Only one patch can be in flight. New operations accumulate while waiting for acknowledgement and become the next patch. The host returns an acknowledgement for the accepted revision or a negative response/resync request if revisions diverge. SDK code handles those control frames; plugin code normally calls only model mutation methods.

Typed `RendererView.set_items()` performs a stable-ID diff and chooses insert/update/remove/move operations automatically. Prefer it over hand-written raw patches for renderer views.

## Visibility and Recovery

`model.visible` mirrors the last host visibility update. Register `model.on_visibility(handler)` or `renderer_view.on_visibility(handler)` to pause optional polling, media work, or expensive recomputation.

While a view is hidden:

- mutations update the local model;
- patches are not sent individually;
- the model is marked for a fresh snapshot;
- the snapshot is sent when the view becomes visible again.

Do not maintain a second hidden-view queue. Continue updating the SDK model and let visibility recovery coalesce the result.

If a patch is rejected or the host requests resynchronization, the SDK resends its current model. This makes local model correctness important: do not mutate returned copies and assume the SDK saw the change; call `update`, `set_items`, or `snapshot`.

## Events and Context Menus

### Raw model events

`model.on_event(component_id, event, handler)` registers an explicit handler and returns it. `off_event(component_id, event)` removes it. Component-tree handlers are normally attached through component constructors or `component.on(...)` and collected during a snapshot.

Event routing requires:

- the correct view instance;
- a stable component/root ID;
- an event supported by that component or renderer;
- a registered handler in the current snapshot/model.

Replacing a component snapshot drops handlers belonging to removed components.

### Typed renderer events

Every `RendererView` supports:

| Method | Handler input | Purpose |
| --- | --- | --- |
| `on_select(handler)` | `NativeViewNode` | Single selection or title action selection. |
| `on_activate(handler)` | `NativeViewNode` | Double-click/Enter-style activation. |
| `on_request_children(handler)` | `NativeViewNode` | Lazy child request for a node marked with children. |
| `on_context_menu(handler)` | `NativeViewNode` | Return a `ContextMenu` component for the selected row/node. May return an awaitable. |

The typed facade maps event IDs back to the original node object. If IDs are duplicated or replaced unexpectedly, the handler cannot resolve the correct item.

Dynamic context-menu providers should return `ContextMenu(...)` or `None`. The host can merge plugin-provided items with manifest `view/context` commands. Handle selection through the returned menu's `on_select` callback.

## View-Local Routes

A view instance has a host-owned route stack. Routing changes the logical content shown by plugin code; it does not create another contributed view.

| Member | Effect |
| --- | --- |
| `route` | Current route from the last host sync; initial value is `home`. |
| `route_stack` | Copy of the synchronized route stack. |
| `route_params` | Copy of parameters for the current route. |
| `on_route(handler)` | Register `handler(route, params)` for every route sync. |
| `push_route(route, params=None, callback=None)` | Push a new route. |
| `replace_route(route, params=None, callback=None)` | Replace the top route. |
| `goto_route(route, params=None, callback=None)` | Navigate to a route using host goto semantics. |
| `pop_route(callback=None)` | Pop the current route. |

Render route-specific content after `on_route` receives the synchronized state. Do not optimistically mutate `route_stack`; the host is authoritative. Route parameters must be serializable values.

## Typed Renderer Facades

Import typed nodes from `pyrite_sdk.api.native_views` and icons from `pyrite_sdk.api.icons`.

| Factory | Manifest renderer | Facade | Accepted primary items |
| --- | --- | --- | --- |
| `views.tree(...)` | `native.tree` | `TreeView` | `TreeItem` |
| `views.virtual_list(...)` | `native.virtualList` | `VirtualListView` | `VirtualListItem` |
| `views.table(...)` | `native.table` | `TableView` | `TableRowItem` plus `TableColumn` configuration |
| `views.form(...)` | `native.form` | `FormView` | `FormField` |
| `views.markdown(...)` | `native.markdown` | `MarkdownView` | `MarkdownContent`; normally use `set_markdown` |
| `views.log(...)` | `native.log` | `LogView` | `LogEntry` |
| `views.outline(...)` | `native.outline` | `OutlineView` | `OutlineItem` |
| `views.variable_inspector(...)` | `native.variableInspector` | `VariableInspectorView` | `VariableScope`, `VariableEntry`, `LoadMoreEntry`, `ViewPlaceholder` |

All factories accept `view_id`, optional `instance_id`, `title`, and `actions`. Renderer-specific options are listed below.

Core `RendererView` members:

- `view_id`, `instance_id`, `visible`
- `items`: copy of typed user items
- `nodes`: copy of published wire nodes including view metadata/actions
- `set_items(items)`: validate typed nodes and publish a diff
- `set_props(**props)`: merge renderer configuration and republish
- `set_actions(actions)`: replace title actions and republish
- `show_placeholder(label, state='empty', icon=Icons.info_outline, icon_color=None)`
- lifecycle/event methods described above

## Typed Node Reference

### Shared enums

`ChildrenState` values:

- `unloaded`: children exist but have not been requested.
- `loading`: a child request is in progress.
- `loaded`: current children are available.
- `error`: loading failed; update the item or show an error placeholder.

`IconColor` values: `primary`, `secondary`, `tertiary`, `muted`, and `error`.

### Data nodes

| Type | Constructor fields | Effect |
| --- | --- | --- |
| `TreeItem` | `id`, `label`, optional `parent_id`, `icon`, `has_children`, `children_state`, extra metadata | Flat hierarchical node; parent links establish the tree. |
| `VirtualListItem` | `id`, `label`, optional `icon`, extra metadata | One flat list row. |
| `TableRowItem` | `id`, `cells`, extra metadata | Row whose `cells` keys match column IDs. |
| `TableColumn` | `id`, `label`, optional `width`, `flex`, `frozen`, `sortable` | Table layout and sort capability. Prefer either fixed width or flex according to the column role. |
| `FormField` | `id`, `label`, `value`, `kind='text'`, optional `options` | Host form input. Kinds: `text`, `number`, `boolean`, `select`; select options are `{value, label, disabled?}` maps. |
| `MarkdownContent` | `text`, optional `id='content'` | Markdown segment. `set_markdown` replaces it with one content node. |
| `LogEntry` | `id`, `message`, `level='info'`, optional `timestamp` | Log row. Use stable unique IDs even when messages repeat. |
| `OutlineItem` | `id`, `label`, optional `parent_id`, `icon`, `icon_color`, `has_children`, `children_state`, `kind`, `detail`, `line`, `column` | Symbol outline entry with optional editor location. |
| `VariableEntry` | `id`, `name`, optional `type_name`, `value`, `parent_id`, `icon`, `icon_color`, `has_children`, `children_state` | Runtime value/property entry. |
| `VariableScope` | `id`, `name`, optional `error`, `has_children` | Styled top-level runtime scope; error text changes its icon/tone. |
| `LoadMoreEntry` | `id`, `parent_id`, `progress`, optional `label` | Paging row with role `loadMore`. |
| `ViewPlaceholder` | `state`, `label`, optional `icon`, `icon_color` | Empty/loading/error message instead of content. Prefer `show_placeholder`. |

Icons must be `Icons.<name>` values, not plain strings. Arbitrary extra metadata on generic nodes is preserved and can be used by plugin handlers.

`VariableEntry.update_fields(...)` updates value/icon/children state in the Python object. Call `set_items` afterward to publish the change.

## Renderer Configuration

### Tree

Factory/configure options:

- `expanded_ids`: initially expanded node IDs.
- `selected_id`: selected node.
- `indent`: indentation in logical pixels.
- `searchable`: enable host tree search behavior.
- `empty_label`: message when no rows exist.

Lazy loading sequence:

1. Publish a node with `has_children=True` and `children_state=ChildrenState.unloaded`.
2. Handle `on_request_children`.
3. Mark it loading and publish.
4. Add child nodes with `parent_id=<parent-id>`.
5. Mark the parent loaded and publish once, preferably through `set_items`.

### Virtual list

Options:

- `item_count`: total logical rows, which may exceed currently loaded items.
- `item_height`: fixed row height.
- `selected_id`: selected row.
- `empty_label`: empty message.

Use a component-tree `VirtualList` when range callbacks are required directly. The typed facade presents item data and selection/activation but does not expose a typed range-request callback.

### Table

Factory options:

- `columns`: iterable of `TableColumn`.
- `row_count`: total logical row count.
- `row_height`: fixed row height.
- `show_header`: show/hide headers.
- `selected_id`: selected row ID.
- `sort_column`: active column ID.
- `sort_ascending`: sort direction.
- `empty_label`: empty message.

Call `set_columns()` when columns change. Each row's `cells` map should include values for the relevant column IDs. Use the component-tree `DataTable` when direct sort/range callbacks are required.

### Form

`FormView` uses `FormField` nodes. Kinds map to native inputs:

- `text` -> `TextField`
- `number` -> `NumberField`
- `boolean` -> `Switch`
- `select` -> `Select`

The typed form facade currently presents fields but does not attach high-level change handlers. Use a component tree for interactive form submission and controlled values.

### Markdown

- `set_markdown(value)` replaces content.
- `on_link_tap(handler)` receives the activated URL string.

Use a component-tree `Markdown` when it must be combined with arbitrary controls in one view.

### Log

- `configure(item_height=None, empty_label=None)`
- `append(LogEntry)`
- `extend(iterable)`
- `clear()`

These methods replace/diff the complete local list. Bound retained history in long-running services instead of growing it indefinitely.

### Outline

Use `OutlineItem` with parent links and stable IDs derived from document identity plus symbol location/identity. Before revealing a location, ensure the outline result is not stale relative to the document revision.

### Variable inspector

Use runtime reference/generation information to create stable IDs for the current backend generation. Represent scopes with `VariableScope`, values with `VariableEntry`, and paging with `LoadMoreEntry`. On backend restart, discard all old entries and references and rebuild from sessions/scopes.

## View Actions and Placeholders

`ViewAction(id, label, icon, on_trigger)` adds an icon action to the host title bar. The icon must be `Icons.<name>`. The callback receives the event payload.

`ViewMenuAction(id, label, items, icon=Icons.more_vert, on_trigger=...)` adds a declarative title-bar menu. `items` use the menu entry types from `ui-components.md`. Its trigger receives the selected-item payload.

Use manifest `view/title` commands for static, discoverable actions that should participate in command activation and `when` enablement. Use `ViewAction` for session-local actions tied directly to a renderer facade. Both can appear together.

`show_placeholder` replaces content with a centered host-owned message. Useful states include `empty`, `loading`, and `error`; the state string is plugin-defined except that `error` receives error styling.

## Tab Instances

`plugin.tabs.create_view(view_id, title=None, expansion=False, callback=...)` asks the host to allocate a tab for a view declared in the same manifest.

The typed callback receives `instance=TabViewInstance` or `error=`. `TabViewInstance` contains:

- `plugin_id`
- `session_id`
- `view_id`
- `instance_id`

After success:

1. Create a model/facade with `instance_id=instance.instance_id`.
2. Set its initial snapshot/items and event handlers.
3. Call `open()` if the flow requires explicit opening.
4. Store per-instance state keyed by `instance_id`.

`expansion=True` requests the host's expanded tab presentation. It is a placement option, not tree expansion.

## Limits and Invariants

| Limit/invariant | Value or rule |
| --- | --- |
| Snapshot nodes | Maximum 20,000 top-level model nodes. |
| Patch operations | Maximum 2,000 operations in one transmitted patch. Additional queued operations are sent later. |
| View payload | Maximum 2 MiB encoded JSON for a snapshot or patch. |
| Component tree | Maximum 5,000 component nodes. |
| Component depth | Maximum 32 levels. |
| In-flight patches | One per view instance. |
| Node identity | Stable, unique top-level `id` for renderer data and patch targets. |
| Component identity | Stable, unique `props.id` for events/controllers inside a component tree. |
| Closed model | Terminal; create a new model to reopen a new instance. |

Large data should be paged or virtualized. Do not use 20,000 nodes as a target size; it is a hard guardrail.

## Selection Guide

| Need | Choose |
| --- | --- |
| Arbitrary layout with controls, menus, media, or Canvas | One component-tree root in a `native.form` contribution. |
| Hierarchical navigation with lazy children | `native.tree` + typed tree facade. |
| Large flat results | `native.virtualList`; use component `VirtualList` for explicit range callbacks. |
| Structured sortable data | `native.table`; use component `DataTable` for explicit sort/range callbacks. |
| Simple host-owned settings rows | Typed `native.form`; use component tree for interactive validation/submission. |
| Standalone formatted documentation | `native.markdown`. |
| Streaming bounded diagnostics | `native.log`. |
| Source symbols and reveal behavior | `native.outline`. |
| Runtime scopes and lazy objects | `native.variableInspector`. |
| Multiple copies of one declared view | Host-created tabs with separate instance IDs. |
