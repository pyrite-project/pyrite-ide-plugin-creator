# Native Component UI

The public component layer is a host-neutral declarative schema. Python constructors produce nodes shaped like:

```text
{"type": "Button", "props": {...}, "children": [...], "events": {...}}
```

The SDK replaces callable handlers with boolean event markers before transmission and keeps the callable in the local view model. The host sends back the event name and payload; it never receives executable Python.

## Contents

- [Component fundamentals](#component-fundamentals)
- [Layout and structure](#layout-and-structure)
- [Content and media](#content-and-media)
- [Input controls](#input-controls)
- [Actions and menus](#actions-and-menus)
- [Data components](#data-components)
- [Page scaffolding](#page-scaffolding)
- [Event payloads](#event-payloads)
- [Controllers](#controllers)
- [Canvas v2](#canvas-v2)
- [Component checklist](#component-checklist)

## Component Fundamentals

Import builders from `pyrite_sdk.api.components`. Each builder returns a `Component` dict.

```python
from pyrite_sdk.api.components import Button, Column, Text

root = Column(
    Text("Ready"),
    Button(id="run", label="Run", on_press=lambda payload: print(payload)),
)
```

Use `component.on(event, handler)` to attach or replace a handler and keep chaining. Use `component.id` to read the optional `props.id`. Use `component.to_json()` only for diagnostics; the view model performs the normal wire conversion.

Rules:

- Component IDs are required for controls, data widgets, controllers, and events. Make them unique within a view instance.
- A leaf component cannot have children.
- A single-child component accepts at most one direct child.
- `Tabs` accepts only `Tab` children; `AppBar` accepts only `IconButton`, `Menu`, or `Dropdown` children.
- Put multiple children inside a many-child layout component. Do not rely on Flutter constructor behavior or invent props not listed here.
- Component schema validation permits a maximum of 5,000 nodes and depth 32.
- Optional `None` props are omitted from the wire node. Use explicit `False`, `0`, or `""` when those values have meaning.

## Layout and Structure

All spacing values are logical pixels. `gap` separates adjacent children; it is not padding around the component.

| Builder/signature | Props | Children and effect |
| --- | --- | --- |
| `Row(*children, id=None, gap=None, align=None, justify=None)` | `gap`; `align`: `start`, `center`, `end`, `stretch`; `justify`: `start`, `center`, `end`, `spaceBetween`, `spaceAround` | Many. Lays children horizontally. |
| `Column(*children, id=None, gap=None, align=None, justify=None)` | Same as `Row` | Many. Lays children vertically. |
| `Flex(*children, id=None, direction=None, flex=None, gap=None)` | `direction`: `horizontal` or `vertical`; optional `flex` and `gap` | Many. Use `flex` when the host should allocate remaining main-axis space. |
| `Grid(*children, columns, id=None, gap=None)` | Required positive `columns`; optional `gap` | Many. Places children in a fixed column count. |
| `Wrap(*children, id=None, gap=None, run_gap=None)` | `gap` between items and `runGap` between wrapped runs | Many. Wraps to available width. |
| `SplitView(*children, id=None, direction=None, initial_ratio=None)` | `direction`: `horizontal` or `vertical`; initial ratio | Many. Divides resizable panes. |
| `Tabs(*children, id=None, selected=None)` | Selected `Tab.id` | Many but only `Tab`; emits `change`. |
| `Tab(child=None, id, label, icon=None)` | Required ID/label; optional Material icon | Exactly one optional child, the tab body. |
| `Section(*children, id=None, title=None, collapsible=None, collapsed=None)` | Header title and collapse state | Many. Emits `toggle` when a collapsible header changes. |
| `Toolbar(*children, id=None, dense=None)` | `dense` compacts the toolbar | Many. Use for compact actions/status. |

`Flex` and `SplitView` are scroll/layout boundaries. Give nested lists stable IDs so their host-local scroll/expansion state survives patches.

## Content and Media

| Builder/signature | Props | Effect |
| --- | --- | --- |
| `Text(value, id=None, style=None, muted=None, max_lines=None)` | `style`: `body`, `caption`, `title`, `heading`, `code`; optional muted/max lines | Displays text. `value` must be a string; convert numbers before passing. |
| `Icon(name, id=None, size=None)` | Required `MaterialIcon`, optional size | Displays a host Material icon. Use `Icons.<name>`. |
| `Image(src, id=None, width=None, height=None, fit=None)` | Required `PluginResource`; `fit`: `contain`, `cover`, `fill`, `none` | Loads a packaged bitmap resource. |
| `Video(src, id=None, width=None, height=None, fit=None, autoplay=None, looping=None, muted=None, show_controls=None)` | Required `PluginResource`; media flags and same fit values | Displays a host video player. |
| `Markdown(value, id=None, on_link_tap=None)` | Markdown string | Renders Markdown and emits `linkTap` with a typed `MarkdownLinkEvent`. |
| `CodeBlock(code, id=None, language=None, show_line_numbers=None)` | Code text, optional language and line numbers | Renders syntax-oriented code content. |
| `Badge(label, id=None, tone=None)` | `tone`: `neutral`, `info`, `success`, `warning`, `danger` | Compact status label. |

Resources:

```python
logo = plugin.resources.asset("assets/logo.png")
preview = Image(logo, id="logo", width=96, height=96, fit="contain")
```

`Resources.asset` rejects absolute paths, backslashes, `..`, NUL characters, and paths outside `assets/`. Canvas images use the same `PluginResource` type.

## Input Controls

Every input requires a stable `id`. Event handlers receive a payload with the current value under `value`.

| Builder/signature | Props | Events and value rules |
| --- | --- | --- |
| `TextField(*, id, value=None, placeholder=None, label=None, enabled=None, multiline=None, on_change=None, on_submit=None)` | Text value, hint/label, enabled flag, multiline | `change` is host-debounced; `submit` means confirmed. Payload `{value: str}`. |
| `NumberField(*, id, value=None, min=None, max=None, step=None, label=None, enabled=None, on_change=None, on_submit=None)` | Numeric value/range/step, label, enabled | `change`/`submit`; payload `{value: number}` or a null value while input is incomplete. |
| `Select(*, id, options, value=None, label=None, enabled=None, on_change=None)` | Required iterable of option maps or `SelectOption`; selected value | `change`; payload `{value: string}`. |
| `Checkbox(*, id, value=None, label=None, enabled=None, on_change=None)` | Boolean value, label, enabled | `change`; payload `{value: bool}`. |
| `Switch(*, id, value=None, label=None, enabled=None, on_change=None)` | Boolean value, label, enabled | `change`; payload `{value: bool}`. |
| `Slider(*, id, value=None, min=None, max=None, step=None, enabled=None, on_change=None)` | Numeric value/range/step, enabled | `change`; payload `{value: number}`. |

Use `enabled=False` to disable a control. Do not use a stale local value to overwrite host edits on every patch; update the model only when the plugin state intentionally changes.

`SelectOption(value, label, disabled=False)` is the typed option helper. Its `value` and `label` properties expose the fixed fields.

## Actions and Menus

| Builder/signature | Props/children | Events and effect |
| --- | --- | --- |
| `Button(*, id, label, icon=None, variant=None, enabled=None, on_press=None)` | Variant: `primary`, `secondary`, `ghost`, `danger`; optional icon | `press` with `{}`. |
| `IconButton(*, id, icon, tooltip=None, enabled=None, on_press=None)` | Required Material icon; optional tooltip/enabled | `press` with `{}`. |
| `Menu(*, id, items, label=None, icon=None, tooltip=None, enabled=None, icon_only=None, alignment=None, offset_x=None, offset_y=None, use_root_overlay=None, child=None, on_select=None)` | Required menu entries; optional one trigger child. Alignment: `bottomStart`, `bottomEnd`, `topStart`, `topEnd`. `iconOnly` defaults false; root overlay defaults true. | `select`, converted to `MenuEvent`. A child is one trigger, not a list. |
| `MenuBar(*, id, items, on_select=None)` | Required top-level menu entries | `select`, converted to `MenuEvent`. |
| `ContextMenu(child=None, *, id, items, enabled=None, on_select=None)` | Required entries and optional one target child | `select`, converted to `MenuEvent`. Return one from a dynamic context-menu provider. |
| `Dropdown(*, id, items, label=None, on_select=None)` | Required item maps, optional label | `select` with `{itemId: ...}`. |
| `Dialog(*children, id, title=None, open=None, on_close=None)` | Many content children; optional title/open state | `close` with `{result: ...}`. `controller.show/close` can drive it. |
| `Tooltip(child=None, id=None, message)` | Required message and one optional child | Host tooltip wrapper; no custom event. |

Typed menu entries:

| Type | Fields and effect |
| --- | --- |
| `MenuShortcut(key, primary=False, control=False, shift=False, alt=False, meta=False)` | Shortcut display/metadata. `primary` represents the platform primary modifier. |
| `MenuItem(id, label, icon=None, trailing_icon=None, shortcut=None, enabled=None, visible=None, tone=None, close_on_select=None)` | Ordinary actionable item. `tone` is host-defined styling metadata; `visible=False` removes it. |
| `MenuDivider(label=None)` | Visual separator, optionally labeled. |
| `MenuCheckboxItem(checked=False, **kwargs)` | `MenuItem` with a checked state. |
| `MenuRadioItem(selected=False, **kwargs)` | `MenuItem` with a selected state. |
| `Submenu(label, children, id=None, icon=None, enabled=None, visible=None)` | Nested menu entries. |

`MenuEvent` fields are `item_id`, `item_type`, `checked`, `selected`, `target_id`, and `target_type`. Missing optional fields return `None`.

## Data Components

| Builder/signature | Main props | Events |
| --- | --- | --- |
| `VirtualList(*, id, items=None, item_count=None, item_height=None, selected_id=None, empty_label=None, on_select=None, on_activate=None, on_request_range=None, on_context_menu=None)` | Loaded `items`, logical count, fixed height, selected ID, empty label | `select`/`activate` with `{itemId}`; `requestRange` with `{start, count}`; dynamic `contextMenuRequest`. |
| `TreeView(*, id, nodes=None, expanded_ids=None, selected_id=None, indent=None, searchable=None, empty_label=None, on_select=None, on_activate=None, on_expand=None, on_collapse=None, on_request_children=None, on_context_menu=None)` | Flat `TreeNode` list, expanded IDs, selected ID, indent, searchable flag, empty label | `select`, `activate`, `expand`, `collapse`, `requestChildren` with `{nodeId}`; `contextMenu` (right-click coordinates) and dynamic `contextMenuRequest`. |
| `DataTable(*, id, columns, rows=None, row_count=None, row_height=None, show_header=None, selected_id=None, sort_column=None, sort_ascending=None, empty_label=None, on_select=None, on_activate=None, on_sort=None, on_request_range=None, on_context_menu=None)` | Required `TableColumn` list, rows/count/height/header/selection/sort | `select`/`activate` with `{rowId}`; `sort` with `{columnId}`; `requestRange` with `{start, count}`; dynamic context menu. |
| `PropertyGrid(*, id, entries, on_select=None, on_expand=None)` | Required `PropertyEntry` list | `select`/`expand` with `{nodeId}`. The host also supports collapse, activation, child requests, and dynamic context menus when the corresponding event markers are present. |

Typed data helpers:

| Type | Fields |
| --- | --- |
| `ListItem` | `id`, `label`, optional `icon`, arbitrary metadata. |
| `TreeNode` | `ListItem` plus `parent_id`, `has_children`. |
| `TableRow` | `id`, `cells` map, arbitrary metadata. |
| `TableColumn` (component) | `id`, `label`, optional `width`, `flex`, `frozen`, `sortable`. |
| `PropertyEntry` | `id`, `name`, `value`, `type_name`, `parent_id`, `has_children`, arbitrary metadata. |
| `RangeRequest` | `start` and `count` properties from a range event. |

Large data guidance:

- Set `item_count`/`row_count` to the logical total and keep only the loaded window in `items`/`rows`.
- Use `RangeRequest.start` and `.count` to fetch the requested window.
- Keep IDs stable when windows slide; do not use the visible index as a permanent identity.
- Return a dynamic context menu as a `ContextMenu` component, not a plain list.

## Page Scaffolding

| Builder | Contract |
| --- | --- |
| `AppBar(*actions, id=None, title=None)` | Many children, but direct children may only be `IconButton`, `Menu`, or `Dropdown`. The host adds manifest title actions separately. |
| `Scaffold(*body, id=None, app_bar=None)` | Many children. An optional `app_bar` is placed before the body; the host gives the body a bounded main-axis extent so lists and split views can scroll. |

Use `Scaffold` as the single root when a view needs a title bar and body. Do not put arbitrary `Text` or layout children directly under `AppBar`.

## Event Payloads

The following payload keys are emitted by the host component layer:

| Component/event | Payload |
| --- | --- |
| Button/IconButton `press` | `{}` |
| TextField/NumberField `change`/`submit` | `{value: ...}` |
| Select/Checkbox/Switch/Slider `change` | `{value: ...}` |
| Tabs `change` | `{id: tab_id}` |
| Section `toggle` | `{collapsed: bool}` |
| Menu/MenuBar/ContextMenu `select` | Menu event fields such as `itemId`, `itemType`, `checked`, `selected`, `targetId`, `targetType`. |
| Dropdown `select` | `{itemId: id}` |
| Dialog `close` | `{result: ...}` |
| Markdown `linkTap` | `{href: url}`; `MarkdownLinkEvent.href` exposes it. |
| VirtualList `select`/`activate` | `{itemId: id}` |
| VirtualList `requestRange` | `{start: int, count: int}` |
| TreeView `select`/`activate`/`expand`/`collapse`/`requestChildren` | `{nodeId: id}` |
| TreeView `contextMenu` | `{nodeId: id, x: number, y: number}` |
| DataTable `select`/`activate` | `{rowId: id}` |
| DataTable `sort` | `{columnId: id}` |
| DataTable `requestRange` | `{start: int, count: int}` |
| PropertyGrid `select`/`activate`/`expand`/`collapse`/`requestChildren` | `{nodeId: id}` |
| Canvas `tap`/`drag`/`hover`/`pointer` | Renderer-defined map. Tap commonly includes `x`, `y`, and `elementId`; drag includes `phase`, coordinates, and deltas. |

Handlers should accept `payload` and use `.get(...)` for optional keys. Do not assume a double-click event if the component only declares `activate`.

## Controllers

Access `component.controller` after the component has been mounted in a view snapshot. Every method accepts an optional callback. Calling a controller before the component has a `props.id` or before it is bound to a `ViewModel` raises locally.

### Base controller

Available for every component:

| Method | Effect |
| --- | --- |
| `is_mounted(callback=None)` | Ask whether the host currently mounts the component. |
| `ensure_visible(alignment=0.5, animated=True, callback=None)` | Scroll the containing surface so the component is visible; alignment is 0..1. |
| `get_bounds(callback=None)` | Return host layout bounds. |
| `request_focus(callback=None)` | Request keyboard/input focus. |
| `unfocus(callback=None)` | Remove focus. |

### Text and number fields

`TextField.controller`:

- `get_text`
- `set_text(text)`
- `clear`
- `select_all`
- `get_selection`
- `set_selection(start, end=None)`; omitted end selects the caret position.
- `replace_selection(text)`

`NumberField.controller` inherits all text methods and adds:

- `get_value`
- `set_value(value)`
- `increment`
- `decrement`

### Virtual list

`VirtualList.controller`:

- `select(id)` and `clear_selection()`
- `reveal_item(id, animated=True)`
- `jump_to_index(index)` and `animate_to_index(index)`
- `scroll_by(delta, animated=True)`
- `get_visible_range()`

### Tree and property grid

`TreeView.controller`:

- `select(id)`, `clear_selection()`
- `reveal(id, animated=True)`
- `expand(id)`, `collapse(id)`, `toggle(id)`
- `expand_all()`, `collapse_all()`
- `is_expanded(id)`
- `get_visible_nodes()`

`PropertyGrid.controller` inherits every tree method and adds `activate(id)`.

### Data table

`DataTable.controller`:

- `select_row(id)`, `clear_selection()`
- `reveal_row(id, animated=True)`
- `reveal_cell(row_id, column_id, animated=True)`
- `jump_to_row(index)`, `animate_to_row(index)`
- `get_visible_range()`

### Tabs, sections, and split views

| Controller | Methods |
| --- | --- |
| `Tabs` | `select(id)`, `next()`, `previous()`, `get_selected()` |
| `Section` | `expand()`, `collapse()`, `toggle()`, `is_expanded()` |
| `SplitView` | `get_ratios()`, `set_ratio(index, ratio)`, `set_ratios(ratios)`, `reset()` |

Ratios are host layout fractions. Keep the number of values equal to the pane count and clamp plugin-provided values to a sensible range.

### Media and Markdown

| Controller | Methods |
| --- | --- |
| `Video` | `play()`, `pause()`, `seek_to(position_ms)`, `set_volume(volume)`, `set_speed(speed)`, `set_looping(looping)`, `get_state()`, `enter_fullscreen()`, `exit_fullscreen()` |
| `Image` | `reload()`, `evict_cache()`, `get_intrinsic_size()` |
| `Markdown` | `scroll_to_anchor(anchor)`, `get_anchor_offset(anchor)`, `select_all()`, `copy_selection()` |

Use milliseconds for video positions and a normalized volume expected by the host. Do not inline bitmap bytes into a Canvas or component payload.

### Menus, dialogs, and Canvas

| Controller | Methods |
| --- | --- |
| `Menu` | `open()`, `close()`, `toggle()`, `is_open()` |
| `MenuBar` | `open_menu(id)`, `close()`, `is_open()` |
| `Dropdown` | `open()`, `close()`, `select(id)`, `get_selected()`, `is_open()` |
| `ContextMenu` | `show(x=None, y=None)`, `close()`, `is_open()` |
| `Dialog` | `show()`, `close(result=None)`, `is_open()` |
| `Canvas` | `push_ops(ops, layer=None)`, `set_ops(ops, layer=None)`, `clear()`, `clear_layer(layer)`, `hit_test(x, y)` |

Controller callbacks receive the host response fields. Keep them tolerant just like other SDK callbacks.

## Canvas v2

Import helpers from `pyrite_sdk.api.canvas` (often as `canvas`). Canvas operations are plain JSON-compatible dictionaries with an `op` discriminator. Coordinates are logical content-space pixels; angles are radians and positive clockwise. Point helpers accept either a flat list `[x0, y0, ...]` or `(x, y)` pairs.

### Color tokens

`canvas.Color` and `canvas.color` are the same callable factory. Pass literal `#RRGGBB` or `#AARRGGBB` strings, or use theme tokens:

`primary`, `on_primary`, `secondary`, `on_secondary`, `surface`, `on_surface`, `on_surface_variant`, `surface_container_highest`, `outline`, `error`, and `on_error`.

For an arbitrary role use `canvas.color.theme("roleName")`. Theme tokens resolve in the host's current light/dark theme.

### Gradients and paint

| Helper | Parameters | Purpose |
| --- | --- | --- |
| `linear_gradient(frm, to, colors, stops=None, tile_mode=None)` | Two points, color list, optional normalized stops/tile mode | Linear shader. |
| `radial_gradient(center, radius, colors, stops=None, focal=None, tile_mode=None)` | Center/radius/color list and optional focal/stops/tile mode | Radial shader. |
| `paint(color=None, stroke_width=None, style=None, stroke_cap=None, stroke_join=None, opacity=None, blend_mode=None, shader=None, anti_alias=None)` | Paint attributes | Shared style for geometry. `style` is normally `fill` or `stroke`. |

`None` values are omitted. Keep paint maps reusable when many operations share a style.

### Geometry operations

| Helper | Wire op and parameters | Effect |
| --- | --- | --- |
| `line(x1, y1, x2, y2, *, paint, id=None)` | `line` | Draw a segment. |
| `polyline(points, *, paint, id=None)` | `polyline` | Draw connected segments through points. |
| `rect(x, y, w, h, *, paint, id=None)` | `rect` | Axis-aligned rectangle. |
| `rrect(x, y, w, h, *, paint, radius=None, rx=None, ry=None, id=None)` | `rrect` | Rounded rectangle; use `radius` or explicit radii. |
| `circle(cx, cy, r, *, paint, id=None)` | `circle` | Circle. |
| `oval(x, y, w, h, *, paint, id=None)` | `oval` | Oval in a bounding rectangle. |
| `arc(x, y, w, h, start_angle, sweep_angle, *, paint, use_center=None, id=None)` | `arc` | Arc of a bounding oval; `use_center` closes to center when true. |
| `points(mode, points, *, paint, id=None)` | `points` | Host point mode such as points/lines/polygon, according to the Canvas schema. |
| `polygon(points, *, paint, closed=None, id=None)` | `polygon` | Polygon from point list; `closed` controls closure. |

An optional `id` gives hit testing and semantic tap payloads an element identity. It does not make an operation interactive by itself.

### Paths

Build path command dictionaries and pass them to `path`:

| Helper | Command |
| --- | --- |
| `move_to(x, y)` | Move current point. |
| `line_to(x, y)` | Straight segment. |
| `quad_to(x1, y1, x, y)` | Quadratic curve. |
| `cubic_to(x1, y1, x2, y2, x, y)` | Cubic curve. |
| `close()` | Close the current contour. |
| `path(commands, *, paint, fill_rule=None, id=None)` | Draw the assembled path. |

`fill_rule` is host-defined (`nonZero`/`evenOdd` are typical schema values). Keep commands JSON-compatible.

### Text and images

`text(x, y, value, *, size=None, family=None, weight=None, italic=None, color=None, align=None, max_width=None, id=None)` draws text. `value` is a string; `size` is logical pixels; `max_width` bounds layout.

`image(src, x, y, *, width=None, height=None, src_x=None, src_y=None, src_w=None, src_h=None, opacity=None, id=None)` draws a packaged image. `src` must be `plugin.resources.asset("assets/file.png")` and is sent as a resource URI; raw paths and bytes are rejected.

### Clipping, layers, and grouping

| Helper | Effect |
| --- | --- |
| `clip_rect(x, y, w, h, anti_alias=None)` | Clip to a rectangle. |
| `clip_rrect(x, y, w, h, radius, anti_alias=None)` | Clip to a rounded rectangle. |
| `clip_path(commands, fill_rule=None, anti_alias=None)` | Clip to a path. |
| `save()` / `restore()` | Save/restore Canvas state. Keep pairs balanced. |
| `save_layer(bounds=None, opacity=None)` | Save an offscreen layer with optional bounds/opacity. |
| `group(*ops, opacity=None, transform=None, clip=None)` | Bundle operations with optional group transform/clip/opacity. |

### Transforms

| Helper | Effect |
| --- | --- |
| `translate(dx, dy)` | Translate the coordinate system. |
| `scale(sx, sy=None)` | Scale; omit `sy` for uniform scale. |
| `rotate(radians, px=None, py=None)` | Rotate around optional pivot. |
| `matrix(affine=None, m4=None)` | Supply exactly one affine matrix or 4x4 matrix representation. Passing both or neither raises `ValueError`. |

### Persistent base versus controller overlay

```python
surface = Canvas(
    id="diagram",
    width=640,
    height=480,
    ops=[canvas.rect(0, 0, 640, 480, paint=canvas.paint(color=canvas.color.surface))],
)

# After the component is mounted:
surface.controller.push_ops(
    [canvas.circle(120, 80, 5, paint=canvas.paint(color="#FFCC00"))],
    layer="cursor",
)
```

- `Canvas(ops=[...])` is the persistent base model. It survives ordinary view patches and is reconstructed by a snapshot.
- `CanvasController.push_ops` appends to an ephemeral overlay layer.
- `CanvasController.set_ops` replaces an ephemeral layer.
- `clear()` clears the overlay; `clear_layer(name)` clears one layer.
- Overlay operations are lost on resync or visibility restoration. Recreate persistent geometry in `props.ops` and use overlays only for transient selection/cursor/drag visuals.
- Controller operation arguments are capped at 2 MiB, just like view payloads.

`hit_test(x, y)` asks the host which semantic operation ID is under a point. Set operation IDs and handle the result; do not replicate host hit-testing math in Python.

### Canvas interaction

Set `interactive=True` to enable host-local interaction. `viewport` can carry host viewport configuration such as `scale`, `minScale`, and `maxScale`. Only semantic events cross the bridge:

- `tap`: click/tap, commonly `{x, y, elementId}`.
- `drag`: gesture lifecycle with `phase` (`start`, `update`, `end`), coordinates, and deltas.
- `hover`: throttled pointer hover.
- `pointer`: throttled low-level pointer data.

The host handles pan/zoom and throttling. Keep high-frequency work in Canvas host-local behavior and debounce plugin reactions.

## Component Checklist

- Use a single root component in each free-form view snapshot.
- Give every interactive/control/data component an `id`.
- Use only listed props and enum values; Python snake_case is converted to wire camelCase.
- Use typed Material icons and plugin resources.
- Wrap multiple children in a many-child layout; respect `Tab`/`AppBar` restrictions.
- Keep event handlers tolerant of optional payload keys and update plugin state deliberately.
- Use controllers only after mount and provide callbacks for host results.
- Keep Canvas persistent ops small, balanced, and JSON-compatible; use overlay layers for transient marks.
- Test component validation errors by parsing the view payload before handing off.
