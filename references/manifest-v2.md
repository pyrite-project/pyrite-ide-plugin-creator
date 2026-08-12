# Manifest v2 Reference

This reference describes the complete public `plugin.toml` contract for PyriteIDE plugins using protocol v1.

## Contents

- [Required shape](#required-shape)
- [Top-level fields](#top-level-fields)
- [Contribution rules](#contribution-rules)
- [Navigation containers](#navigation-containers)
- [Views](#views)
- [Commands](#commands)
- [Menus](#menus)
- [Configuration](#configuration)
- [Icons and assets](#icons-and-assets)
- [Activation events](#activation-events)
- [Permissions](#permissions)
- [Platforms](#platforms)
- [`when` expressions](#when-expressions)
- [Complete example](#complete-example)
- [Failure checklist](#failure-checklist)

## Required Shape

Manifest v2 uses top-level fields and arrays of tables. Do not use the legacy `[general]`, `[permissions]`, or `[platform]` tables.

The six required fields must be written explicitly:

```toml
manifest_version = 2
id = "acme.python-tools"
name = "Python Tools"
version = "1.0.0"
type = "ui"
protocol_version = 1
```

The parser rejects unknown fields, wrong TOML types, duplicate entries, unsupported values, and contribution IDs outside the plugin namespace.

## Top-Level Fields

| Field | TOML type | Required | Default | Purpose and constraints |
| --- | --- | --- | --- | --- |
| `manifest_version` | integer | yes | none in a file | Must equal `2`. |
| `id` | string | yes | none | Stable plugin identity and contribution namespace. It is not a display label. |
| `name` | string | yes | none | Non-empty display name. |
| `version` | string | yes | none | Non-empty plugin version. The manifest does not enforce SemVer syntax, but SemVer is recommended. |
| `type` | string | yes | none | Exactly `ui`, `service`, or `data`. |
| `protocol_version` | integer | yes | none in a file | Must equal `1`. |
| `python_version` | string | no | omitted | Packaging/runtime compatibility declaration, for example `"3.14"`. It does not select a private interpreter for this plugin. |
| `author` | string | no | `""` | Human-facing author metadata. |
| `description` | string | no | `""` | Human-facing plugin summary. |
| `icons` | inline/table | no | omitted | Full-color and monochrome package icons below `assets/`. |
| `activation_events` | array of strings | no | `[]` | Conditions that start a plugin session. |
| `permissions` | array of strings | no | `[]` | Host capabilities requested by the plugin. |
| `platforms` | array of strings | no | `[]` | Supported host platforms. |
| `contributes` | table | no | empty | Static navigation, views, commands, menus, and settings declarations. |

ID rules:

- A plugin ID starts with an ASCII letter or digit and may contain letters, digits, `_`, `-`, and dot-separated segments.
- Windows reserved names such as `con`, `nul`, `com1`, and `lpt1` are invalid as the first plugin ID segment.
- Every contribution ID must start with `<plugin-id>.`, except a navigation container may equal the plugin ID exactly.
- Contribution IDs are unique without regard to letter case, including across contribution kinds.

Examples of valid IDs: `python-tools`, `acme.python_tools`, `acme.tools-debug`.

## Contribution Rules

Only these keys are allowed under `contributes`:

```toml
[[contributes.navigation_containers]]
[[contributes.views]]
[[contributes.commands]]
[[contributes.menus]]
[[contributes.configuration]]
```

A UI plugin must declare at least one navigation container. References are local to the same manifest: a view must target a declared container, and a menu must target declared commands and views.

Every contribution supports `order = 0` unless noted otherwise. Lower values sort before higher values. Use explicit spaced values such as `10`, `20`, and `30` when ordering matters.

## Navigation Containers

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Container identity. It may equal the plugin ID. |
| `title` | yes | Non-empty navigation label. |
| `icon` | no | Material or asset icon reference. |
| `location` | no | `primary` by default; also accepts `secondary`. |
| `order` | no | Navigation ordering integer. |
| `when` | no | Visibility condition. |

Example:

```toml
[[contributes.navigation_containers]]
id = "acme.python-tools"
title = "Python"
icon = { material = "code" }
location = "primary"
order = 100
when = "workspace.opened"
```

Use one container for related views. Add another only when the plugin genuinely needs a separate navigation destination.

## Views

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Namespaced view ID used by `plugin.views` and activation events. |
| `container` | yes | ID of a navigation container in this manifest. |
| `title` | yes | Non-empty view title. |
| `renderer` | yes | One supported native renderer. |
| `icon` | no | Material or asset icon. |
| `order` | no | Ordering inside the container. |
| `when` | no | Visibility condition. |

Supported renderers:

| Renderer | Intended data |
| --- | --- |
| `native.tree` | Hierarchical file, resource, or category nodes. |
| `native.virtualList` | Large or lazily loaded flat lists. |
| `native.table` | Rows with declared columns, sorting, and range loading. |
| `native.form` | General component-tree UI and form fields. |
| `native.markdown` | Markdown content and link activation. |
| `native.log` | Appendable timestamped log entries. |
| `native.outline` | Document symbols with kind, detail, and source position. |
| `native.variableInspector` | Runtime scopes, values, lazy children, and paging. |

Example:

```toml
[[contributes.views]]
id = "acme.python-tools.outline"
container = "acme.python-tools"
title = "Outline"
renderer = "native.outline"
icon = { material = "account_tree_outlined" }
order = 10
when = "editor.language == 'python' && editor.hasDocument"
```

The renderer is a contract. Match it to the view facade and node types described in `ui-views.md`.

## Commands

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Namespaced command ID registered with `plugin.commands`. |
| `title` | yes | Command palette/menu label. |
| `icon` | no | Material or asset icon. |
| `order` | no | Ordering where commands are presented. |
| `when` | no | Enablement condition. |

Example:

```toml
[[contributes.commands]]
id = "acme.python-tools.refresh"
title = "Refresh Outline"
icon = { material = "refresh" }
when = "editor.language == 'python' && editor.hasDocument"
```

Declare `onCommand:acme.python-tools.refresh` when executing this command should activate an otherwise inactive plugin. Register the same exact ID in Python.

## Menus

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `location` | yes | One supported menu surface. |
| `command` | yes | Command ID declared in this manifest. |
| `view` | no | View ID for view-scoped locations. |
| `group` | no | Non-empty grouping label; group names are plugin-defined. |
| `order` | no | Ordering inside the location/group. |
| `when` | no | Visibility condition for the menu entry. |

Locations:

- `view/title`: action in a contributed view title bar; set `view`.
- `view/context`: action in the context menu of a contributed view; set `view`.
- `navigation/context`: action in a navigation container context menu.
- `commandPalette`: globally discoverable command palette entry.

Example:

```toml
[[contributes.menus]]
location = "view/title"
view = "acme.python-tools.outline"
command = "acme.python-tools.refresh"
group = "navigation"
order = 10
when = "editor.hasDocument"
```

The menu's `when` controls visibility. The referenced command's `when` controls enablement, so a visible menu can be disabled when the command condition is false.

## Configuration

Manifest configuration is plugin-owned user configuration. It is separate from `plugin.settings`, which accesses global IDE settings.

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Namespaced configuration ID used by `plugin.configuration`. |
| `title` | yes | User-facing setting label. |
| `type` | yes | `string`, `integer`, `number`, `boolean`, or `array`. |
| `description` | no | User-facing explanation. |
| `default` | no | JSON-compatible default matching `type`; `null` is permitted. |
| `enum` | no | Non-null JSON-compatible choices matching `type`. |
| `order` | no | Ordering in the settings UI. |
| `when` | no | Visibility condition. |

Rules:

- A non-null default must match the declared type.
- Every enum value must match the type and cannot be null.
- If both a non-null default and enum are present, the default must occur in the enum.
- Integers must fit a signed 64-bit value; numeric values must be finite.
- Arrays and nested values must be JSON-compatible. TOML dates and other non-JSON objects are invalid.

Examples:

```toml
[[contributes.configuration]]
id = "acme.python-tools.showPrivate"
title = "Show Private Variables"
type = "boolean"
description = "Include names beginning with an underscore"
default = false
order = 10

[[contributes.configuration]]
id = "acme.python-tools.sortMode"
title = "Outline Sort Mode"
type = "string"
default = "source"
enum = ["source", "name", "kind"]
order = 20
```

Read, write, list, and subscribe through `plugin.configuration`; see `sdk-operations.md` for exact calls and callback behavior.

## Icons and Assets

Plugin package icons require both forms:

```toml
icons = { full = "assets/icon.png", monochrome = "assets/icon-mono.png" }
```

Contribution icons use exactly one source:

```toml
icon = { material = "refresh" }
icon = { asset = "assets/actions/refresh.png" }
```

Asset constraints:

- Start with `assets/`.
- Use `/`, not `\`.
- Stay below the plugin's assets directory; do not use absolute paths, drive prefixes, `..`, or NUL characters.
- Refer to a packaged file.
- Use `Icons.<name>` in Python for component and renderer icons; do not pass arbitrary icon strings.

## Activation Events

Supported forms:

| Event | Effect |
| --- | --- |
| `onStartup` | Start during plugin activation scanning. Use for an always-on service or conventional data contribution. |
| `onView:<view-id>` | Start when the declared view is opened. |
| `onCommand:<command-id>` | Start before the declared command executes. |
| `onLanguage:<language-id>` | Valid language activation declaration. Use only when the target PyriteIDE integration initiates language activation; do not make it the sole path when broader compatibility matters. |

Events must be unique. `onView` and `onCommand` targets must exist in the same manifest. Language IDs may contain letters, digits, `_`, `+`, `.`, and `-`.

Typical choices:

- UI plugin: one `onView` per independently activatable view, plus `onCommand` for commands that must work before a view opens.
- Service plugin: `onStartup` for a continuous background service, or command/view activation when startup work is unnecessary.
- Data plugin: one-shot `on_contribute`; `onStartup` communicates intent even though data plugins are managed as contributions.

## Permissions

Declare only supported strings:

| Permission | Allows |
| --- | --- |
| `ui.view` | Contributed view operations and clipboard writes. |
| `ui.navigate` | Reserved navigation capability; do not add it unless a public operation requires it. |
| `ui.notify` | `plugin.message` notifications. |
| `file.read` | Workspace/local file queries and reads. |
| `file.write` | File creation, mutation, transfer, and write operations; write authorization also satisfies reads for this resource. |
| `board.read` | Device-board filesystem queries and reads. |
| `board.write` | Device-board mutation and transfer; write authorization also satisfies reads. |
| `editor.read` | Editor text, selection, search, tab queries, documents, and symbols. |
| `editor.write` | Editor mutations, reveal/open/close, and decorations; write authorization also satisfies reads. |
| `persistence.read` | Read plugin-private persisted values. |
| `persistence.write` | Set/delete/clear plugin-private data; write authorization also satisfies reads. |
| `tab.create` | Create a tab instance of a contributed view. |
| `tab.manage` | Manage plugin tabs when a public management operation is available. |
| `settings.read` | Read global IDE settings and manifest configuration values. |
| `settings.write` | Change global IDE settings and manifest configuration values; write authorization also satisfies reads. |
| `serial.read` | List/status/read serial connections. |
| `serial.write` | Connect, send, execute, reset, and change serial behavior; write authorization also satisfies reads. |
| `data.read` | Read themes, localization bundles, and stubs providers. |
| `data.write` | Contribute/register/revoke theme, localization, and stubs data; write authorization also satisfies reads. |
| `dialog.show` | Open host dialogs such as folder selection. |
| `runtime.inspect` | Query runtime sessions, scopes, variables, children, and object information. |

There are no broad `ui`, `file`, or `data` permissions in Manifest v2. Use dotted action names exactly.

## Platforms

Allowed values are:

```toml
platforms = ["windows", "linux", "macos", "android"]
```

Use lowercase names. List only platforms the plugin code, dependencies, assets, and external integrations actually support. Platform declarations are compatibility metadata and validation input; plugin code must still handle environment-specific behavior through `plugin.env` when necessary.

## `when` Expressions

Available context keys:

- `editor.language`
- `editor.hasDocument`
- `runtime.language`
- `runtime.state`
- `device.connected`
- `workspace.opened`
- `plugin.enabled`
- `view.active`

Operators and precedence:

1. `!`
2. `&&`
3. `||`

Use parentheses to override precedence. Comparisons support only `==` and `!=`. Literals may be quoted strings, booleans, integers, or decimal numbers.

Valid examples:

```toml
when = "workspace.opened && editor.hasDocument"
when = "editor.language == 'python' && runtime.state != 'running'"
when = "device.connected || (runtime.language == 'python' && !editor.hasDocument)"
```

Unsupported constructs include regex operators, `<`, `>`, `in`, `contains`, function calls, and null literals. Keep expressions below 4096 UTF-16 code units, 256 tokens, and 64 nesting levels. A bare key uses truthiness: false, zero, an empty string, or a missing value is false.

## Complete Example

```toml
manifest_version = 2
id = "acme.python-tools"
name = "Python Tools"
version = "1.0.0"
type = "ui"
protocol_version = 1
python_version = "3.14"
author = "Acme"
description = "Outline and runtime inspection tools"
icons = { full = "assets/icon.png", monochrome = "assets/icon-mono.png" }
activation_events = [
  "onView:acme.python-tools.outline",
  "onView:acme.python-tools.variables",
  "onCommand:acme.python-tools.refresh",
]
permissions = [
  "ui.view",
  "editor.read",
  "settings.read",
  "runtime.inspect",
]
platforms = ["windows", "linux", "macos", "android"]

[[contributes.navigation_containers]]
id = "acme.python-tools"
title = "Python"
icon = { material = "code" }
location = "primary"
order = 100

[[contributes.views]]
id = "acme.python-tools.outline"
container = "acme.python-tools"
title = "Outline"
renderer = "native.outline"
icon = { material = "account_tree_outlined" }
order = 10

[[contributes.views]]
id = "acme.python-tools.variables"
container = "acme.python-tools"
title = "Variables"
renderer = "native.variableInspector"
icon = { material = "data_object" }
order = 20
when = "runtime.language == 'python' && workspace.opened"

[[contributes.commands]]
id = "acme.python-tools.refresh"
title = "Refresh Variables"
icon = { material = "refresh" }
when = "runtime.language == 'python' && workspace.opened"

[[contributes.menus]]
location = "view/title"
view = "acme.python-tools.variables"
command = "acme.python-tools.refresh"
group = "navigation"
order = 10
when = "runtime.language == 'python' && workspace.opened"

[[contributes.configuration]]
id = "acme.python-tools.showPrivate"
title = "Show Private Variables"
type = "boolean"
description = "Include private names in the variable inspector"
default = false
order = 20
when = "runtime.language == 'python' && workspace.opened"
```

## Failure Checklist

- Confirm all six required top-level fields are explicit.
- Confirm `type` is `ui`, `service`, or `data` and protocol is `1`.
- Confirm a UI plugin declares a navigation container.
- Confirm every contribution ID uses the exact plugin namespace and is unique case-insensitively.
- Confirm view containers, menu commands, menu views, and activation targets exist.
- Confirm renderers, permissions, platforms, menu locations, configuration types, and context keys use the supported spellings.
- Confirm defaults and enum values match the declared configuration type.
- Confirm icon assets exist below `assets/` and Material icon names are valid.
- Parse and validate the manifest before packaging; syntax-only TOML parsing does not catch semantic errors.
