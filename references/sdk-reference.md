# PyriteSDK Reference

Use this file for verified facts about the published PyriteSDK package. If behavior matters, check the official documentation or validate against the installed package with a focused smoke test.

Documentation URL: .

## Package Map

- Plugin classes: `pyrite_sdk.core.plugin`
- UI API: `pyrite_sdk.api.ui`
- File and board APIs: `pyrite_sdk.api.file` and `pyrite_sdk.api.board`
- Editor API: `pyrite_sdk.api.editor`
- Settings API: `pyrite_sdk.api.settings`
- Persistence API: `pyrite_sdk.api.persistence`
- Data APIs: `pyrite_sdk.api.data`
- Serial API: `pyrite_sdk.api.serial`
- Path API: `pyrite_sdk.api.path`
- Packager CLI: `pyrsdk`

## Runtime Model

PyriteSDK plugins are Python programs that run a WebSocket server. PyriteIDE connects as the client.

Important environment/path facts:

- `PYRITE_IDE_PLUGIN_PORT` is required by `Bridge.__init__`; do not call `plugin.start()` outside PyriteIDE unless it is set.
- `PYRITE_IDE_PLUGIN_ID` is used in output/path routing.
- `PYRITE_IDE_PLUGIN_DIR`, `PYRITE_IDE_PLUGIN_DATA_DIR`, `PYRITE_IDE_PLUGIN_CACHE_DIR`, and `PYRITE_IDE_PLUGIN_TEMP_DIR` are path shortcuts.
- `BasePlugin.assets` is set after the IDE returns the plugin/assets path. If code needs bundled assets, use `self.path.get(PathScope.ASSETS, callback=...)` or wait until `self.assets` exists.
- Use `pathlib.Path` for paths. Avoid Windows backslash string pitfalls.

## Plugin Classes

Use current classes, not old generic `Plugin` docs.

| Class | Use For | Entrypoint |
| --- | --- | --- |
| `UiPlugin` | Visible pages, UI events, editor/file/board tools | `plugin.start()` |
| `ServicePlugin` | Background services without pages | `plugin.start()` |
| `DataPlugin` | One-shot theme/i18n/stubs contributions | `plugin.run_once()` |

`UiPlugin` and `ServicePlugin` require `on_start`. `DataPlugin` requires `on_contribute`; `on_start` calls it and then stops when pending responses are complete.

## plugin.toml

Observed shape:

```toml
[general]
name = "My Plugin"
id = "my-plugin"
version = "0.1.0"
author = "Your Name"
type = "ui"

[permissions]
ui = true
persistence = true

[platform]
linux = true
macos = true
windows = true
android = true
```

Use `type = "ui"` for `UiPlugin`, `type = "service"` for `ServicePlugin`, and `type = "data"` for `DataPlugin`, including theme, i18n, and stubs contributions. Use `auto_start = true` mainly for services that should run without opening a page.

Keep permissions minimal:

| Code Uses | Permission |
| --- | --- |
| `pages`, `router`, `bridge.let`, RFW UI | `ui` |
| `plugin.file.*` | `file` |
| `plugin.board.*` | `board` |
| `plugin.editor.*` | `editor` |
| `plugin.persistence.*` | `persistence` |
| `plugin.settings.*` | `settings` |
| `plugin.serial.*` | `serial` |
| `plugin.theme.*`, `plugin.i18n.*`, `plugin.stubs.*` | `data` |

Boolean permissions normally expand to all standard actions for that resource. If exact action lists matter, verify against the published documentation.

## UI API Notes

Typical imports:

```python
from pyrite_sdk.api.ui import *
from pyrite_sdk.core.plugin import UiPlugin
from pyrite_sdk.models.consts import Package, PathScope, Ui
```

Page construction pattern:

```python
page = Page(packages=[Package.core.widgets, Package.core.material])
root = NewWidget(Ui.root).add_to(page)
scaffold = Scaffold(app_bar=AppBar(title=Text("Title"))).add_to(root)
body = SafeArea().add_to(scaffold)
content = Padding(EdgeInsets.all(12)).add_to(body)
Column(cross_axis_alignment=CrossAxisAlignment.stretch).add_to(content).add(Text("Hello"))
return page
```

Use snake_case wrapper names and enum values. Examples:

- `Alignment.top_center`, not `Alignment.topCenter`
- `CrossAxisAlignment.stretch`
- `TextStyle(font_size=13, font_weight=FontWeight.bold)`
- `EdgeInsets.only(top=8)`

Single-child widgets can receive only one direct child. Wrap multiple generated widgets in `Column`, `Row`, `Stack`, or another multi-child widget before placing them inside `Padding`, `Container`, `Expanded`, `SafeArea`, `Center`, `Align`, buttons, or cards.

Event callbacks:

```python
TextField(
    value=data.prompt,
    on_changed=Event(lambda value="", **_: plugin.bridge.let(data.prompt, value)),
)
ElevatedButton(
    on_pressed=Event(lambda prompt="", **_: plugin.send(prompt), args={"prompt": data.prompt})
).add(Text("Send"))
```

Use `plugin.bridge.let(data.some_key, value)` for dynamic values. Rebuild and refresh for structural changes:

```python
self.pages["home"] = build_home_page(...)
self.bridge.refresh(call_on_refresh=False)
```

Do not emit raw `set data...` RFW statements unless you have verified the parser accepts the exact expression. Prefer Python callbacks.

## Markdown And Text Input

Use SDK wrappers, not custom markdown parsing:

- `MarkdownBlock(data, selectable=True, ...)`
- `MarkdownWidget(data, shrink_wrap=True, ...)`
- `Markdown(data, ...)`

Markdown code styling parameters include:

- `code_block_padding`
- `code_block_margin`
- `code_block_decoration`
- `code_block_text_style`
- `code_block_style_not_matched`
- `code_block_language`
- `code_block_theme`
- `inline_code_text_style`

Use user-provided code font settings only when the user has configured a font; do not auto-set editor or markdown fonts. `TextStyle(background_color=...)` serializes to `backgroundColor` for inline code.

`TextField` supports `value`, `initial_value`, `decoration`, `keyboard_type`, `text_input_action`, `min_lines`, `max_lines`, `enabled`, `read_only`, `obscure_text`, `on_changed`, `on_submitted`, and `on_tap`. Current host callbacks return text as `value`.

## API Families

Most SDK API wrappers are asynchronous/callback-oriented even when docs describe request/response tables. Treat callbacks as `**kwargs` and inspect live responses when payload shape matters.

Common response keys seen in current usage:

- `data`: many file, editor, persistence, and path values
- `path`: path request responses
- `content`: some file-read or generated helper responses
- `error`, `message`, `code`: failures

Useful methods:

- File: `get_root_dir`, `get_file_list`, `read_file`, `write_file`, `create_file`, `create_folder`, `rename`, `delete`, `exists`, `is_file`, `is_directory`, `open_file`, `open_folder`, `save_current_file`, `save_current_file_as`
- Board: similar file operations for board files, plus `download_file`, `download_selected_board_item`, `get_corresponding_file_path`
- Editor: `get_text`, `set_text`, `insert_text`, `replace_range`, cursor/selection, clipboard, undo/redo, search, tabs, ghost text, scrolling
- Persistence: `get(group, key, callback)`, `set(group, key, value)`, `delete`, `list_groups`, `list_keys`, `clear`
- Settings: `get(name)`, `set(name, value)`, plus grouped helpers under `settings.editor`, `settings.lsp`, `settings.serial`, `settings.terminal`, `settings.micropython_stubs`
- Data: `theme.contribute`, `i18n.contribute`, `stubs.contribute`, `revoke`, `get`, `list`
- Serial: `list_ports`, `get_status`, `connect`, `disconnect`, `send`, `send_command`, `read`, `run_python`, `set_baud_rate`, `set_auto_reconnect`
- Path: `path.plugin()`, `data()`, `cache()`, `temp()`, `get(scope, callback)`
- Message: `message.info`, `success`, `warning`, `error`

## Packaging

Install the SDK while developing:

```bash
pip install pyrite-sdk
```

Package with the `pyrsdk` CLI:

```bash
pyrsdk package /path/to/plugin -p Darwin --arch arm64 -rf /path/to/plugin/requirements.txt -a build/plugin.zip
```

Common options:

- `-i` or `--interactive`
- `-p Android --arch arm64-v8a`
- `-p Darwin --arch arm64` or `--arch x86_64`
- `--compile-app`, `--compile-packages`, `--cleanup`
- `--exclude <relative-path>`
- `--pip-tool uv|pip`

The plugin ZIP root must contain `plugin.toml` and `__main__.py`.

## Documentation Notes

Prefer published documentation and runtime smoke tests over copied snippets from old examples. If older snippets use synchronous-looking calls, raw widget names such as `Button`, or raw `onPressed`, rewrite them with current SDK wrappers such as `ElevatedButton(on_pressed=Event(...))`.
