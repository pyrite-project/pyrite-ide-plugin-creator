# Manifest v2 reference

`plugin.toml` sits at the root of the plugin package, next to `__main__.py`. The
host parses it with `pyrite_sdk.models.manifest.load_file()`, which is strict:
unknown keys, wrong types, and dangling references are hard errors at install
time. Validating locally is always cheaper than reinstalling.

**Contents**: [Top-level fields](#top-level-fields) · [Activation events](#activation-events) ·
[Permissions](#permissions) · [Contributes](#contributes) · [when expressions](#when-expressions) ·
[Icons and assets](#icons-and-assets) · [Complete examples](#complete-examples) ·
[Common mistakes](#common-manifest-mistakes)

```python
from pyrite_sdk.models.manifest import load_file
load_file("my-plugin/plugin.toml")     # raises ManifestValidationError(code, message)
```

`ManifestValidationError.code` is one of:

`manifest_missing`, `manifest_invalid_toml`, `manifest_missing_version`,
`manifest_unsupported_version`, `manifest_invalid_schema`,
`manifest_invalid_plugin_id`, `manifest_invalid_permission`,
`manifest_invalid_contribution_id`, `manifest_contribution_conflict`,
`manifest_missing_navigation_container`, `manifest_unknown_renderer`,
`manifest_rfw_renderer_unsupported`, `manifest_invalid_when`,
`manifest_unknown_icon`, `manifest_invalid_activation_event`.

## Top-level fields

| Key | Type | Required | Rules |
| --- | --- | --- | --- |
| `manifest_version` | int | yes | Must be exactly `2`. v1 manifests are rejected. |
| `id` | string | yes | `^[A-Za-z0-9][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)*$`; Windows device names (`con`, `nul`, `com1`, …) rejected. |
| `name` | string | yes | Non-blank display name. |
| `version` | string | yes | Non-blank. Semver is conventional, not enforced. |
| `type` | string | yes | `"ui"`, `"service"`, or `"data"`. |
| `protocol_version` | int | yes | Must be `1`. |
| `python_version` | string | no | Runtime bundled by the packager: `"3.12"`, `"3.13"`, `"3.14"`. Omitted → `3.14`. |
| `author` | string | no | Free text. |
| `description` | string | no | Free text, shown in the plugin list. |
| `icons` | table | no | `full` and `monochrome`, both required when the table exists, both `assets/…`. |
| `activation_events` | array of strings | no | See below. Empty means the host decides (installed-but-lazy). |
| `permissions` | array of strings | no | Allowlist below; duplicates rejected. |
| `platforms` | array of strings | no | Subset of `windows`, `linux`, `macos`, `android`; duplicates rejected. |
| `contributes` | table | no | Contributions below. |

Unknown top-level keys are rejected — `extra="forbid"` plus an explicit allowlist.

## Activation events

| Event | Meaning |
| --- | --- |
| `onStartup` | Launch with the IDE. `manifest.auto_start` is true when present. |
| `onView:<view id>` | Launch when that contributed view is first shown. |
| `onCommand:<command id>` | Launch when that contributed command runs. |
| `onLanguage:<language id>` | Launch when a document of that language opens. Language ids match `^[A-Za-z0-9][A-Za-z0-9_+.-]*$`. |

View and command targets must be declared in this same manifest. Duplicates are
rejected. A plugin with no activation event relies on the host's default policy,
which is why most templates list at least one.

## Permissions

Every permission is `resource.action`. Calls fail with `permission_denied` when the
matching permission is absent, so declare exactly what the code uses. The mapping
below is the host's own (`pyrite-ide/lib/core/sdk/permissions.dart`), which is what
actually decides — the SDK does not enforce anything client-side.

| Permission | Unlocks |
| --- | --- |
| `ui.view` | `clipboard.set_text`. Also the umbrella most UI plugins declare, even though view-model calls are public (see below). |
| `ui.navigate` | Accepted by the validator and declared by templates; the current host does not gate route ops on it. |
| `ui.notify` | `message.show/info/success/warning/error` |
| `file.read` | `file.get_file_list`, `get_root_dir`, `read_file`, `exists`, `is_file`, `is_directory`, `get_focus_file_node`, `get_focus_folder_node`, `get_unique_name`, `open_file`, `open_folder`, `upload_file`, `upload_selected_local_file_item` |
| `file.write` | `file.write_file`, `create_file`, `create_folder`, `delete`, `rename`, `copy_file`, `move_file`, `save_current_file`, `save_current_file_as` |
| `board.read` | `board.get_dir_list`, `get_root_dir`, `read_file`, `exists`, `is_file`, `is_directory`, `get_focus_*`, `get_corresponding_file_path`, `open_file`, `download_file`, `download_selected_board_item` |
| `board.write` | `board.write_file`, `delete_file`, `delete_folder`, `rename` |
| `editor.read` | `editor.get_text`, `get_line_count`, `get_line_text`, `get_selected_text`, `get_cursor_position`, `get_selection`, `can_undo`, `can_redo`, `find`, `find_regex`, `clear_search`, `copy`; `documents.get_active/get/symbols/get_selection` |
| `editor.write` | `editor.set_text`, `insert_text`, `replace_range`, `clear`, `set_cursor_position`, `set_selection`, `select_all`, `go_to_line`, `undo`, `redo`, `cut`, `paste`, `open_file`, `set_ghost_text`, `clear_ghost_text`, `scroll_to_line`; **`documents.reveal`** |
| `editor.keys` | `editor.capture_keys` / `release_keys` (key hijacking) |
| `persistence.read` | `persistence.get`, `list_groups`, `list_keys` |
| `persistence.write` | `persistence.set`, `delete`, `clear` |
| `tab.create` | `views.open(..., placement=<tab>)` (`sdk.tab.create_view`) |
| `tab.manage` | `editor_tabs.list/activate/close` |
| `settings.read` | `settings.get`, `settings.list`, grouped `settings.*.get_*` |
| `settings.write` | `settings.set`, grouped `settings.*.set_*` |
| `serial.read` | `serial.list_ports`, `get_status`, `read` |
| `serial.write` | `serial.connect/disconnect/send/send_command/run_python/hardware_reset`, `set_baud_rate`, `set_auto_reconnect` |
| `data.read` | `theme.get/list`, `i18n.get/list`, `stubs.get/list/resolve_layers`, `lsp.get/list` |
| `data.write` | `theme.contribute/register_runtime/revoke`, `i18n.*`, `stubs.*`, `lsp.*` |
| `dialog.show` | `dialog.open_file/open_files/open_folder` |
| `runtime.inspect` | `runtime.sessions/state/scopes/variables/children/object_info` |

Public in the host — no permission needed: `sdk.view.open/snapshot/patch/close/focus`,
`sdk.view.route.*`, `sdk.view.component.invoke`, `sdk.configuration.*`,
`sdk.env.get`, `sdk.path.request`, `sdk.events.subscribe/unsubscribe`. The reasoning
is that a plugin managing its own view model, its own routes, or its own declared
configuration is not touching anything the user has not already granted by
installing it. Event subscriptions are allowed to reach the bus, but the bus still
enforces per-topic permissions.

Permissions are declared, not requested at runtime: the IDE surfaces them in the
plugin's permission monitor, and the user installs with them or not at all. Never
widen a permission to make an unrelated bug disappear.

## `contributes`

### `[[contributes.navigation_containers]]`

The sidebar entry a UI plugin hangs off. A `ui` manifest must declare at least one.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | — | May be the bare plugin id, or `<plugin id>.something`. |
| `title` | string | — | Non-blank. |
| `icon` | table | — | `{ material = "…" }` or `{ asset = "assets/…" }`. |
| `location` | string | `"primary"` | `primary` or `secondary`. |
| `order` | int | `0` | Signed 64-bit. |
| `when` | string | — | Visibility expression. |

### `[[contributes.views]]`

A renderable slot inside a container.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | — | Must start with `<plugin id>.`. |
| `container` | string | — | Must match a declared navigation container id. |
| `title` | string | — | Non-blank. |
| `renderer` | string | — | Allowlist below. |
| `icon` | table | — | Material or asset. |
| `order` | int | `0` | |
| `when` | string | — | |

Renderer allowlist (anything else, including `rfw` and `rfw.*`, is rejected):

`native.tree`, `native.virtualList`, `native.table`, `native.form`,
`native.markdown`, `native.log`, `native.outline`, `native.variableInspector`.

The renderer is a promise about the data shape you will send. `native.tree` expects
tree nodes, `native.table` expects columns plus rows, and so on — see
`views-and-renderers.md`. `native.form` is the generic container: it accepts either
a component tree (snapshot) or form fields (typed facade).

### `[[contributes.commands]]`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | — | Must start with `<plugin id>.`. |
| `title` | string | — | Shown in the palette. |
| `icon` | table | — | |
| `order` | int | `0` | |
| `when` | string | — | |

Declaring a command only makes it visible. It does nothing until
`plugin.commands.register(id, handler)` runs in `on_start`. The handler is called as
`handler(args=<dict>, context=<dict>)` and may be `async def`; its return value is
sent back to the host as the command result.

### `[[contributes.menus]]`

Places a command in a host menu.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `location` | string | — | `view/title`, `view/context`, `navigation/context`, `commandPalette`. |
| `command` | string | — | Must match a declared command id. |
| `view` | string | — | Required in practice for `view/title` and `view/context`; must match a declared view id. |
| `group` | string | — | Free-form grouping key. |
| `order` | int | `0` | |
| `when` | string | — | |

### `[[contributes.configuration]]`

Declarative settings the host renders and stores per plugin.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | — | Must start with `<plugin id>.`. |
| `title` | string | — | |
| `type` | string | — | `string`, `integer`, `number`, `boolean`, `array`. |
| `description` | string | `""` | |
| `default` | any | `null` | Must be JSON and match `type`; must appear in `enum` when `enum` is set. |
| `enum` | array | `[]` | Every entry must match `type` and be non-null. |
| `order` | int | `0` | |
| `when` | string | — | |

Read them back with fully-qualified ids:

```python
def on_start(self):
    self.configuration.list(callback=self._on_config)
    self.configuration.on_changed(self._on_config_changed)

def _on_config(self, data=None, error=None, **_):
    for item in data or []:                     # [{"id": "acme.tools.verbose", "value": False}, …]
        key = item["id"].removeprefix("acme.tools.")
        self._config[key] = item["value"]

def _on_config_changed(self, event):
    key = str(event.get("id", "")).removeprefix("acme.tools.")
    self._config[key] = event.get("value")
```

`configuration.get(id)` / `.set(id, value)` use the same fully-qualified id.

## `when` expressions

A deliberately small boolean language evaluated by the host against live context.
It is validated at install time, so a bad expression fails the manifest.

```
runtime.language == 'python' && (workspace.opened || device.connected)
!view.active && editor.hasDocument
```

- Allowed keys: `editor.language`, `editor.hasDocument`, `runtime.language`,
  `runtime.state`, `device.connected`, `workspace.opened`, `plugin.enabled`,
  `view.active`.
- Operators: `&&`, `||`, `!`, `==`, `!=`, parentheses.
- Literals: single- or double-quoted strings, integers/decimals, `true`, `false`.
- Limits: 4096 UTF-16 code units, 256 tokens, 64 levels of nesting.
- A bare key (no comparison) is a truthiness test, e.g. `workspace.opened`.

## Icons and assets

```toml
icons = { full = "assets/icon.png", monochrome = "assets/icon-mono.png" }

[[contributes.commands]]
id = "acme.tools.refresh"
title = "Refresh"
icon = { material = "refresh" }
```

- `{ material = "…" }` must be a name from the SDK's Material table
  (`pyrite_sdk.api.material_icons.MATERIAL_ICON_CODES`, 8825 snake_case names).
  In code the same names are reachable as `Icons.refresh`.
- `{ asset = "assets/…" }` must be a forward-slash relative path below `assets/`,
  must exist as a regular file, and must not escape the plugin directory via `..`
  or a symlink.
- Exactly one source per icon; both or neither is an error.
- Top-level `[icons]` is the plugin's own icon (full + monochrome), not a
  contribution icon.

## Complete examples

### UI plugin

```toml
manifest_version = 2
id = "python-tools"
name = "Python Tools"
version = "1.1.0"
type = "ui"
protocol_version = 1
python_version = "3.14"
author = "PyriteIDE"
description = "Python outline and variable inspection tools"
activation_events = [
  "onView:python-tools.outline",
  "onView:python-tools.variables",
  "onCommand:python-tools.refreshVariables",
]
permissions = ["ui.view", "editor.read", "settings.read", "runtime.inspect"]
platforms = ["windows", "linux", "macos", "android"]

[[contributes.navigation_containers]]
id = "python-tools"
title = "Python"
icon = { material = "code" }
location = "primary"
order = 100

[[contributes.views]]
id = "python-tools.outline"
container = "python-tools"
title = "Outline"
renderer = "native.outline"
icon = { material = "account_tree_outlined" }
order = 10

[[contributes.views]]
id = "python-tools.variables"
container = "python-tools"
title = "Variables"
renderer = "native.variableInspector"
icon = { material = "data_object" }
order = 20
when = "runtime.language == 'python' && workspace.opened"

[[contributes.commands]]
id = "python-tools.refreshVariables"
title = "Refresh Variables"
icon = { material = "refresh" }
when = "runtime.language == 'python' && workspace.opened"

[[contributes.menus]]
location = "view/title"
view = "python-tools.variables"
command = "python-tools.refreshVariables"
group = "navigation"

[[contributes.configuration]]
id = "python-tools.showPrivate"
title = "Show Private Variables"
type = "boolean"
description = "Include private names in the variable inspector"
default = false
```

### Service plugin

```toml
manifest_version = 2
id = "fim-completion"
name = "FIM Completion"
version = "1.0.0"
type = "service"
protocol_version = 1
python_version = "3.14"
author = "Pyrite Project"
description = "Inline fill-in-the-middle completion with ghost text"
activation_events = ["onStartup"]
permissions = ["editor.read", "editor.write", "editor.keys"]
platforms = ["linux", "macos", "windows", "android"]

[[contributes.configuration]]
id = "fim-completion.enabled"
title = "Enable FIM"
type = "boolean"
default = true
order = 1

[[contributes.configuration]]
id = "fim-completion.model"
title = "Model"
type = "string"
default = "deepseek-chat"
order = 2

[[contributes.configuration]]
id = "fim-completion.api_format"
title = "API format"
type = "string"
default = "completions"
enum = ["completions", "chat"]
order = 3
```

A service plugin needs no container and no view — it has no `views` attribute at all.

### Data plugin

```toml
manifest_version = 2
id = "nord-theme"
name = "Nord Theme"
version = "1.0.0"
type = "data"
protocol_version = 1
python_version = "3.14"
author = "Pyrite Project"
activation_events = ["onStartup"]
permissions = ["data.write"]
platforms = ["linux", "macos", "windows", "android"]
```

```python
from pyrite_sdk.core.plugin import DataPlugin


class NordThemePlugin(DataPlugin):
    def on_contribute(self) -> None:
        self.theme.contribute(
            "nord",
            {
                "color.primary": "#5E81AC",
                "color.onPrimary": "#ECEFF4",
                "color.surface": "#ECEFF4",
                "color.onSurface": "#2E3440",
                "dark.color.primary": "#88C0D0",
                "dark.color.surface": "#2E3440",
                "dark.color.onSurface": "#ECEFF4",
            },
        )


plugin = NordThemePlugin()

if __name__ == "__main__":
    plugin.run_once()
```

`DataPlugin.on_start()` calls `on_contribute()` and then stops the bridge once the
contribution round-trips are answered — that is why it exits on its own.

## Common manifest mistakes

| Mistake | Error code |
| --- | --- |
| `type = "ui"` with no navigation container | `manifest_missing_navigation_container` |
| Contribution id without the plugin prefix (`main` instead of `acme.tools.main`) | `manifest_invalid_contribution_id` |
| Same id used for a command and a configuration entry | `manifest_contribution_conflict` |
| `renderer = "rfw.page"` | `manifest_rfw_renderer_unsupported` |
| `renderer = "native.table"` typo (`native.datatable`) | `manifest_unknown_renderer` |
| `when = "runtime.language === 'python'"` | `manifest_invalid_when` |
| `icon = { material = "Refresh" }` (wrong case) | `manifest_unknown_icon` |
| `icon = { material = "refresh", asset = "assets/r.png" }` | `manifest_invalid_schema` |
| `permissions = ["editor.all"]` | `manifest_invalid_permission` |
| `activation_events = ["onView:acme.other"]` (undeclared view) | `manifest_invalid_activation_event` |
| `default = "8"` for `type = "integer"` | `manifest_invalid_schema` |
| `default = 3` with `enum = [1, 2]` | `manifest_invalid_schema` |
| Any unknown key anywhere | `manifest_invalid_schema` |
