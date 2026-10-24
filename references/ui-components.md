# Native UI components

A view renders a list of `Component` nodes. `Component` is a `dict` subclass with
`{"type", "props", "children", "events"}`, so it serializes straight into a
snapshot or patch — you never build wire dictionaries by hand.

**Contents**: [Layout](#layout) · [Page shells](#page-shells-and-grouping) ·
[Text and media](#text-and-media) · [Inputs](#inputs) · [Actions](#actions) ·
[Menus](#menus) · [Dialogs](#dialogs) · [Data components](#data-components) ·
[Canvas](#canvas) · [Controllers](#controllers) · [Styling](#styling) ·
[Composition](#composition-patterns)

```python
from pyrite_sdk.api.components import *
from pyrite_sdk.api.icons import Icons
```

Rules that keep a tree healthy:

- **Give every interactive or patchable node a stable `id`.** Builders that need
  one (`Button`, `IconButton`, `FloatingActionButton`, `TextField`, `Menu`,
  `VirtualList`, `TreeView`, `DataTable`, `Canvas`, `Dialog`, …) mint a random
  `token_hex(16)` when you omit it, which silently breaks patching and event
  routing on the next render.
- **Ids are unique per view instance**, not global. Two instances of the same view
  may reuse the same ids.
- Handlers are **sync** and receive the host payload dict. A handler that returns
  a coroutine is ignored.
- Props set to `None` are dropped before sending, so optional props are simply
  absent.
- `Component.on("eventName", handler)` attaches an event the builders do not wrap;
  the wire form carries `{eventName: true}` and the SDK maps it back to your
  function.

## Layout

| Builder | Key props | Notes |
| --- | --- | --- |
| `Row(*children, id, gap, align, justify)` | `align`: start/center/end/stretch; `justify`: start/center/end/spaceBetween/spaceAround | Horizontal flex |
| `Column(*children, id, gap, align, justify)` | same | Vertical flex |
| `Flex(*children, id, direction, flex, gap)` | `direction`: horizontal/vertical | Generic flex |
| `Stack(*children, id, alignment)` | | Overlay children |
| `Padding(child, id, all_padding, left_padding, right_padding, top_padding, bottom_padding)` | | Pixels |
| `Expanded(child, id, flex)` | | Must sit inside Row/Column/Flex |
| `SizedBox(child, id, width, height)` | | Fixed box; omit `child` for a spacer |
| `Spacer(id, flex)` | | Flexible gap |
| `Align(child, id, alignment, width_factor, height_factor)` | | |
| `Center(child, id, width_factor, height_factor)` | | |
| `Container(child, id, width, height, padding, margin, color, border_radius, alignment, border_color, border_width, style)` | | The general box |
| `Card(child, id, elevation, padding, border_radius, color, margin, style)` | | Elevated surface |
| `AspectRatio(child, aspect_ratio, id)` | | |
| `FittedBox(child, id, fit, alignment)` | | |
| `ConstrainedBox(child, id, min_width, max_width, min_height, max_height)` | | |
| `FractionallySizedBox(child, id, width_factor, height_factor, alignment)` | | |
| `LimitedBox(child, id, max_width, max_height)` | | |
| `SafeArea(child, id, left, top, right, bottom, minimum)` | | |
| `Visibility(child, id, visible, maintain_state, maintain_animation, maintain_size)` | | Prefer this over removing nodes when state must survive |
| `Grid(*children, columns, id, gap)` | | Fixed-column grid |
| `Wrap(*children, id, gap, run_gap)` | | Flowing wrap |
| `Divider(id, height, thickness, indent, end_indent, color)` | | |
| `VerticalDivider(id, width, thickness, indent, end_indent, color)` | | |
| `Tooltip(child, id, message)` | | |

Scrolling containers:

| Builder | Key props |
| --- | --- |
| `SingleChildScrollView(child, id, scroll_direction, reverse, padding, primary)` | |
| `ListView(*children, id, scroll_direction, reverse, padding, item_extent, shrink_wrap)` | Use for modest, fully-materialised lists |
| `GridView(*children, cross_axis_count, id, main_axis_spacing, cross_axis_spacing, padding, shrink_wrap)` | |
| `PageView(*children, id, initial_page, scroll_direction, on_page_changed)` | event: `pageChanged` |

## Page shells and grouping

| Builder | Key props / events |
| --- | --- |
| `Scaffold(*body, id, app_bar)` | Page skeleton: optional `AppBar` plus body |
| `AppBar(*actions, id, title)` | Title bar with action children |
| `Toolbar(*children, id, dense)` | |
| `Section(*children, id, title, collapsible, collapsed)` | controller: `expand/collapse/toggle/is_expanded` |
| `Tabs(*children, id, selected)` | children are `Tab`s; controller: `select/next/previous/get_selected` |
| `Tab(child, id, label, icon)` | |
| `SplitView(*children, id, direction, initial_ratio)` | controller: `get_ratios/set_ratio/set_ratios/reset` |
| `ExpansionTile(*children, id, title, subtitle, initially_expanded, enabled, on_expansion_changed)` | event: `expansionChanged` |
| `Drawer(*children, id, width, elevation, background_color)` | |

## Text and media

| Builder | Key props / events |
| --- | --- |
| `Text(value, id, style, muted, max_lines, color, font_size, font_weight, text_align)` | `style`: `body` / `caption` / `title` / `heading` / `code`, or a dict |
| `SelectableText(value, id, style, max_lines, on_tap)` | event: `tap` |
| `CodeBlock(code, id, language, show_line_numbers)` | Read-only, syntax-highlighted |
| `Markdown(value, id, on_link_tap)` | event: `linkTap`; `on_link_tap` requires an `id` |
| `Badge(label, id, tone, style)` | |
| `Icon(name, id, size, color, semantic_label)` | `name` is `Icons.<snake_case>` |
| `Image(src, id, width, height, fit)` | `src` must be `plugin.resources.asset("assets/…")`; controller: `reload/evict_cache/get_intrinsic_size` |
| `Video(src, id, width, height, fit, autoplay, looping, muted, show_controls)` | `src` must be a `PluginResource`; controller: `play/pause/seek_to/set_volume/set_speed/set_looping/get_state/enter_fullscreen/exit_fullscreen` |
| `CircleAvatar(child, id, radius, background_color, foreground_color, text)` | |
| `Chip(label, id, avatar_icon, delete_icon, enabled, selected, style, on_deleted, on_selected)` | events: `deleted`, `selected` |
| `CircularProgressIndicator(id, value, stroke_width, color, background_color)` | Indeterminate when `value` is omitted |
| `LinearProgressIndicator(id, value, min_height, color, background_color)` | |

## Inputs

All input builders emit `change` with the new value in the payload, and the text
ones also emit `submit`.

| Builder | Key props | Events |
| --- | --- | --- |
| `TextField(id, value, placeholder, label, enabled, multiline, obscure_text, max_lines, min_lines, keyboard_type, style, filled, fill_color, on_change, on_submit)` | | `change`, `submit` |
| `NumberField(id, value, min, max, step, label, enabled, style, on_change, on_submit)` | | `change`, `submit` |
| `Select(id, options, value, label, enabled, style, on_change)` | `options`: `[SelectOption(value=…, label=…, disabled=…)]` | `change` |
| `Checkbox(id, value, label, enabled, style, on_change)` | | `change` |
| `Switch(id, value, label, enabled, style, on_change)` | | `change` |
| `Slider(id, value, min, max, step, enabled, style, on_change)` | | `change` |
| `RangeSlider(id, start, end, min, max, step, enabled, style, on_change)` | | `change` |
| `Radio(id, value, group_value, label, enabled, style, on_change)` | | `change` |
| `SegmentedButton(id, segments, selected, multi_selection_enabled, empty_selection_allowed, enabled, style, on_change)` | | `change` |
| `CheckboxListTile(id, value, title, subtitle, enabled, selected, on_change)` | | `change` |
| `SwitchListTile(id, value, title, subtitle, enabled, selected, on_change)` | | `change` |
| `RadioListTile(id, value, group_value, title, subtitle, enabled, on_change)` | | `change` |
| `ListTile(id, title, subtitle, leading_icon, trailing_icon, dense, enabled, selected, style, on_tap, on_long_press)` | | `tap`, `longPress` |

Controllers: `TextField.controller` / `NumberField.controller` expose
`get_text`, `set_text`, `clear`, `select_all`, `get_selection`, `set_selection`,
`replace_selection`, plus `get_value`, `set_value`, `increment`, `decrement` for
numbers.

## Actions

| Builder | Key props | Events |
| --- | --- | --- |
| `Button(id, label, icon, variant, enabled, style, width, height, tooltip, on_press)` | `variant`: `primary` / `secondary` / `ghost` / `danger` | `press` |
| `TextButton(**kwargs)` | `Button` with `variant="ghost"` | `press` |
| `OutlinedButton(**kwargs)` | `Button` with `variant="secondary"` | `press` |
| `FilledButton(**kwargs)` / `ElevatedButton(**kwargs)` | `Button` with `variant="primary"` | `press` |
| `IconButton(id, icon, tooltip, enabled, style, size, on_press)` | | `press` |
| `FloatingActionButton(id, label, icon, tooltip, extended, small, mini, enabled, style, on_press)` | | `press` |
| `NavigationBar(id, destinations, selected_index, label_behavior, style, on_change)` | | `change` |
| `NavigationRail(id, destinations, selected_index, extended, label_type, style, on_change)` | | `change` |
| `BottomNavigationBar(id, items, current_index, type, on_tap)` | | `tap` |

## Menus

Menu entries are data classes, not components:

```python
from pyrite_sdk.api.components import (
    Menu, MenuItem, MenuCheckboxItem, MenuRadioItem, MenuDivider, Submenu,
    MenuShortcut, ContextMenu,
)

Menu(
    id="acme.menu",
    label="Actions",
    icon=Icons.more_vert,
    items=[
        MenuItem(id="acme.copy", label="Copy", shortcut=MenuShortcut("C", primary=True)),
        MenuDivider(),
        MenuCheckboxItem(id="acme.wrap", label="Word wrap", checked=True),
        Submenu(label="More", children=[MenuItem(id="acme.about", label="About")]),
    ],
    on_select=lambda e: self._on_menu(e.item_id),
)
```

| Builder | Notes |
| --- | --- |
| `MenuItem(id, label, icon, trailing_icon, shortcut, enabled, visible, tone, close_on_select)` | Wire `type: "item"` |
| `MenuCheckboxItem(checked=False, **MenuItem kwargs)` | `type: "checkbox"` |
| `MenuRadioItem(selected=False, **MenuItem kwargs)` | `type: "radio"` |
| `MenuDivider(label=None)` | `type: "divider"` |
| `Submenu(label, children, id, icon, enabled, visible)` | `type: "submenu"` |
| `MenuShortcut(key, primary=False, control=False, shift=False, alt=False, meta=False)` | Platform-aware hint |
| `Menu(...)` | Trigger button; controller: `open/close/toggle/is_open` |
| `MenuBar(items, on_select)` | controller: `open_menu(id)/close/is_open` |
| `ContextMenu(child, items, enabled, on_select)` | controller: `show(x, y)/close/is_open` |
| `Dropdown(items, label, on_select)` | controller: `open/close/select/get_selected/is_open` |

`on_select` receives a `MenuEvent` with `item_id`, `item_type`, `checked`,
`selected`, `target_id`, `target_type`.

For per-row context menus on `VirtualList` / `TreeView` / `DataTable`, pass
`on_context_menu=<callable>`; it receives the row object and must return a
`ContextMenu` component (or `None`, or an awaitable of either).

## Dialogs

```python
Dialog(
    Column(Text("Delete 3 files?"), Row(TextButton(...), FilledButton(...), gap=8), gap=12),
    id="acme.confirm",
    title="Confirm",
    open=True,
    on_close=lambda payload: self._close_dialog(),
)
```

`AlertDialog(*children, id, title, open, on_close)` is the same node with
`type="AlertDialog"`. Toggle `open` through a patch (`update(id, {"open": False})`)
or the controller (`show()`, `close(result)`, `is_open()`). Event: `close`.

`SnackBar(message, id, action_label, duration_ms, on_action)` — event: `action`.
For one-off toasts prefer `plugin.message.info(...)`, which does not need a view.

## Data components

These are virtualised: give them a total count and page in slices rather than
materialising everything.

```python
VirtualList(
    id="acme.files",
    items=[ListItem(id="a.py", label="a.py", icon=Icons.description_outlined)],
    item_count=1200,
    selected_id="a.py",
    on_select=lambda item: self._select(item.id),
    on_activate=lambda item: self._open(item.id),
    on_request_range=lambda req: self._load(req.start, req.count),
)
```

| Builder | Data class | Events |
| --- | --- | --- |
| `VirtualList(id, items, item_count, item_height, selected_id, empty_label, on_select, on_activate, on_request_range, on_context_menu)` | `ListItem(id, label, icon, **data)` | `select`, `activate`, `requestRange` |
| `TreeView(id, nodes, expanded_ids, selected_id, indent, searchable, empty_label, on_select, on_activate, on_expand, on_collapse, on_request_children, on_context_menu)` | `TreeNode(id, label, parent_id, icon, has_children, **data)` | `select`, `activate`, `expand`, `collapse`, `requestChildren` |
| `DataTable(id, columns, rows, row_count, row_height, show_header, selected_id, sort_column, sort_ascending, empty_label, on_select, on_activate, on_sort, on_request_range, on_context_menu)` | `TableColumn(id, label, width, flex, frozen, sortable)`, `TableRow(id, cells)` | `select`, `activate`, `sort`, `requestRange` |
| `PropertyGrid(id, entries, on_select, on_expand)` | `PropertyEntry(id, name, value, type_name, parent_id, has_children, **meta)` | `select`, `expand` |

`RangeRequest` carries `start` and `count`. Controllers: `VirtualList.controller`
(`select`, `clear_selection`, `reveal_item`, `jump_to_index`,
`animate_to_index`, `scroll_by`), `TreeView.controller` (`select`, `reveal`,
`expand`, `collapse`, `toggle`, `expand_all`, `collapse_all`, `is_expanded`,
`get_visible_nodes`), `DataTable.controller` (`select_row`, `reveal_row`,
`reveal_cell`, `jump_to_row`, `animate_to_row`, `get_visible_range`),
`PropertyGrid.controller` (tree methods plus `activate`).

`ListItem` / `TreeNode` / `TableRow` / `PropertyEntry` are dict subclasses, so any
extra keyword becomes metadata on the wire and is readable again from the object
handed back to your handler.

## Canvas

A Canvas is a retained custom-draw surface. Coordinates are content-space logical
pixels; angles are radians, clockwise-positive.

```python
from pyrite_sdk.api import canvas as cv
from pyrite_sdk.api.components import Canvas

Canvas(
    id="acme.plot",
    width=640, height=240,
    interactive=True,
    ops=[
        cv.rect(0, 0, 640, 240, paint=cv.paint(color=cv.Color.surface)),
        cv.line(0, 120, 640, 120, paint=cv.paint(color=cv.Color.outline, stroke_width=1)),
        cv.polyline([(0, 200), (120, 80), (240, 160)], paint=cv.paint(color=cv.Color.primary, stroke_width=2)),
        cv.text(12, 12, "sample", size=12, color=cv.Color.on_surface),
    ],
    on_pointer=lambda payload: self._on_pointer(payload),
)
```

Op helpers: `line`, `polyline`, `rect`, `rrect`, `circle`, `oval`, `arc`, `points`,
`polygon`, `path` (built from `move_to` / `line_to` / `quad_to` / `cubic_to` /
`close`), `text`, `image`, `group`, plus transform and clip ops (`save`,
`restore`, `save_layer`, `translate`, `scale`, `rotate`, `matrix`, `clip_rect`,
`clip_rrect`, `clip_path`).

Paint: `cv.paint(color=…, stroke_width=…, style=…, stroke_cap=…, stroke_join=…,
opacity=…, blend_mode=…, shader=…, anti_alias=…)`, with gradients from
`cv.linear_gradient(...)` / `cv.radial_gradient(...)`.

Colors: hex strings (`"#RRGGBB"`, `"#AARRGGBB"`) or theme tokens from
`cv.Color` (`primary`, `onPrimary`, `secondary`, `surface`, `onSurface`,
`onSurfaceVariant`, `surfaceContainerHighest`, `outline`, `error`, `onError`) or
`cv.Color.theme("role")`.

Two layers: `props.ops` is the persistent base layer (survives snapshots and
resyncs); `canvas.controller.push_ops(ops)` / `set_ops(ops)` write the ephemeral
overlay (lost on resync). Controller also offers `clear`, `clear_layer`,
`hit_test`. Events: `tap`, `drag`, `hover`, `pointer` — each only wired when you
pass a handler, so an idle canvas costs no cross-process traffic.

## Controllers

`component.controller` returns a typed controller for a mounted component. It
requires a stable `id` and a component that is already in a view instance; calls
are routed as `invoke` requests, not patches.

```python
self.field.controller.set_text("hello")
self.tree.controller.expand("src")
self.canvas.controller.push_ops([cv.circle(10, 10, 4, paint=cv.paint(color="#f00"))])
```

Base controller (every component): `is_mounted`, `ensure_visible(alignment,
animated)`, `get_bounds`, `request_focus`, `unfocus`.

## Styling

- `variant` is the sanctioned way to pick a button emphasis.
- `style` is a free-form dict passed to the host's component registry. Its keys are
  host-defined; prefer explicit props (`color`, `font_size`, `font_weight`,
  `border_radius`, `padding`, `margin`, `gap`) and do not invent style keys — an
  unknown key is silently ignored or rejected by the registry, never by the SDK.
- Colors are strings. Use theme-role tokens where a component accepts them so the
  UI follows the active theme; hard-coded hex is fine for data visualisation.
- Spacing is logical pixels; `gap` on `Row`/`Column`/`Flex`/`Grid`/`Wrap` is the
  cheapest way to lay out, and avoids wrapper `Padding` nodes.

## Composition patterns

**Header + scrolling body**

```python
Scaffold(
    Column(
        Row(Text("Files", style="heading"), Spacer(), IconButton(id="acme.reload", icon=Icons.refresh, on_press=self._reload), gap=8),
        Divider(),
        Expanded(ListView(*[ListTile(id=f"row.{i}", title=name) for i, name in enumerate(names)])),
        gap=12,
    )
)
```

**Empty state instead of an empty list**

```python
if not self._items:
    return [Scaffold(Center(Column(Icon(Icons.inbox_outlined, size=32), Text("Nothing here yet", muted=True), gap=8)))]
```

**Keep ids stable across renders.** Derive them from data (`f"row.{path}"`), never
from list position if the list can reorder, and never let the builder generate one.
