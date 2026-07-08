# Pyrite Plugin Patterns

Use these patterns as starting points. Prefer editing existing examples over copying large blocks blindly.

## Choose A Pattern

| Request Shape | Plugin Type | Base Class | Entrypoint |
| --- | --- | --- | --- |
| Page, control panel, chat UI, editor/file action, dashboard | `ui` | `UiPlugin` | `plugin.start()` |
| Watch files, sync data, run a background task | `service` | `ServicePlugin` | `plugin.start()` |
| Theme, language pack, stubs, static data | `data` | `DataPlugin` | `plugin.run_once()` |

## UI Plugin Skeleton

```python
from pyrite_sdk.api.ui import *
from pyrite_sdk.core.plugin import UiPlugin
from pyrite_sdk.models.consts import Package, Ui


def build_home_page(title: str, status: str):
    page = Page(packages=[Package.core.widgets, Package.core.material])
    root = NewWidget(Ui.root).add_to(page)
    scaffold = Scaffold(app_bar=AppBar(title=Text(title))).add_to(root)
    body = SafeArea().add_to(scaffold)
    content = Padding(EdgeInsets.all(12)).add_to(body)
    column = Column(cross_axis_alignment=CrossAxisAlignment.stretch).add_to(content)
    column.add(Text(title, style=TextStyle(font_size=18, font_weight=FontWeight.bold)))
    Padding(EdgeInsets.only(top=8)).add_to(column).add(Text(["状态：", status], soft_wrap=True))
    with Padding(EdgeInsets.only(top=12)).add_to(column):
        row = Row(cross_axis_alignment=CrossAxisAlignment.center)
        button = ElevatedButton(on_pressed=Event(lambda **_: plugin.set_status("已点击"))).add_to(row)
        button.add(Text("运行"))
    return page


class MyPlugin(UiPlugin):
    def __init__(self):
        super().__init__()
        self.status = "就绪"
        self.pages = {}
        self._render()

    def on_start(self):
        print("My Plugin started")
        self.router.goto("home")

    def on_refresh(self):
        self._render()

    def _render(self):
        self.pages = {"home": build_home_page("My Plugin", self.status)}

    def set_status(self, value: str):
        self.status = value
        self._render()
        self.bridge.refresh(call_on_refresh=False)


plugin = None


def main():
    global plugin
    plugin = MyPlugin()
    plugin.start()


if __name__ == "__main__":
    main()
```

Notes:

- Use `Column` or `Row` inside `Padding` whenever there may be more than one child.
- Prefer `Padding`/`margin` for gaps. Use `SizedBox` only when the user wants fixed dimensions or an existing example proves it renders correctly.
- Keep `plugin` global only for callback lambdas that need it; keep state on the plugin instance.

## Settings Page Pattern

```python
def build_settings_page(api_url: str, api_key: str):
    page = Page(packages=[Package.core.widgets, Package.core.material])
    root = NewWidget(Ui.root).add_to(page)
    scaffold = Scaffold(app_bar=AppBar(title=Text("设置"))).add_to(root)
    body = SafeArea().add_to(scaffold)
    scroll = SingleChildScrollView(padding=EdgeInsets.all(14)).add_to(body)
    column = Column(cross_axis_alignment=CrossAxisAlignment.stretch).add_to(scroll)
    column.add(
        TextField(
            value=data.settings_url,
            initial_value=api_url,
            decoration=call("InputDecoration", label_text="API 地址", is_dense=True),
            on_changed=Event(lambda value="", **_: plugin.bridge.let(data.settings_url, value)),
        )
    )
    Padding(EdgeInsets.only(top=16)).add_to(column).add(
        TextField(
            value=data.settings_api_key,
            initial_value=api_key,
            decoration=call("InputDecoration", label_text="API Key", is_dense=True),
            obscure_text=True,
            on_changed=Event(lambda value="", **_: plugin.bridge.let(data.settings_api_key, value)),
        )
    )
    with Padding(EdgeInsets.only(top=16)).add_to(column):
        button = ElevatedButton(
            on_pressed=Event(
                lambda url="", api_key="", **_: plugin.save_settings(url, api_key),
                args={"url": data.settings_url, "api_key": data.settings_api_key},
            )
        )
        button.add(Text("保存"))
    return page
```

Load persisted values with callbacks:

```python
self.persistence.get("group", "api_url", callback=lambda data=None, **_: self._apply_url(data))
self.persistence.set("group", "api_url", value)
```

## Markdown Pattern

```python
MarkdownBlock(
    content,
    selectable=True,
    code_block_padding=EdgeInsets.only(left=12, top=10, right=12, bottom=10),
    code_block_margin=EdgeInsets.symmetric(vertical=7),
    code_block_decoration=BoxDecoration(
        color=color(0xFFF8FAFC),
        border=Border.all(color=color(0xFFE2E8F0)),
        border_radius=BorderRadius.circular(6),
    ),
    code_block_theme="light",
    inline_code_text_style=TextStyle(
        color=color(0xFF0F172A),
        background_color=color(0xFFEFF4FA),
        font_size=13,
    ),
)
```

If the user exposes a code font setting, pass `font_family` only when the setting is non-empty. Do not auto-write user font settings.

## Service Plugin Skeleton

```python
from pyrite_sdk.core.plugin import ServicePlugin


class MyService(ServicePlugin):
    def __init__(self):
        super().__init__()
        self.running = False

    def on_start(self):
        self.running = True
        print("Service started")

    def on_pause(self):
        print("Service paused")

    def on_resume(self):
        print("Service resumed")

    def on_dispose(self):
        self.running = False
        print("Service disposed")


plugin = None


def main():
    global plugin
    plugin = MyService()
    plugin.start()


if __name__ == "__main__":
    main()
```

Use `auto_start = true` in `plugin.toml` only when the service should start without a visible user action. Avoid long blocking loops on the bridge thread; use worker threads or short scheduled work.

## Data Plugin Patterns

Theme:

```python
from pyrite_sdk.core.plugin import DataPlugin


class ThemePlugin(DataPlugin):
    def on_contribute(self):
        self.theme.contribute(
            "my-theme",
            {
                "color.primary": "#5E81AC",
                "color.onPrimary": "#FFFFFF",
                "color.surface": "#FFFFFF",
                "color.onSurface": "#111111",
                "dark.color.primary": "#88C0D0",
                "dark.color.onPrimary": "#111111",
            },
        )


plugin = None


def main():
    global plugin
    plugin = ThemePlugin()
    plugin.run_once()


if __name__ == "__main__":
    main()
```

I18n:

```python
class LanguagePlugin(DataPlugin):
    def on_contribute(self):
        self.i18n.contribute("zh-CN", {"menu.file": "文件"})
        self.i18n.contribute("en", {"menu.file": "File"})
```

MicroPython stubs:

```python
class StubsPlugin(DataPlugin):
    def on_contribute(self):
        root = self.path.plugin() / "stubs"
        self.stubs.contribute(
            provider_id="my-stubs",
            kind="micropython",
            version="1.0.0",
            profiles=[
                {
                    "id": "generic",
                    "label": "Generic",
                    "path": str(root / "generic"),
                    "priority": 10,
                }
            ],
            aliases=["micropython"],
        )
```

## plugin.toml Patterns

UI:

```toml
[general]
name = "My UI Plugin"
id = "my-ui-plugin"
version = "0.1.0"
author = "Your Name"
type = "ui"

[permissions]
ui = true

[platform]
linux = true
macos = true
windows = true
android = true
```

Service:

```toml
[general]
name = "My Service"
id = "my-service"
version = "0.1.0"
author = "Your Name"
type = "service"
auto_start = true

[permissions]
file = true
persistence = true

[platform]
linux = true
macos = true
windows = true
android = true
```

Data:

```toml
[general]
name = "My Data Plugin"
id = "my-data-plugin"
version = "0.1.0"
author = "Your Name"
type = "data"

[permissions]
data = true

[platform]
linux = true
macos = true
windows = true
android = true
```

## Common Tasks

Read a workspace file:

```python
def on_read(**_):
    plugin.file.read_file(
        "/main.py",
        callback=lambda data=None, **cb: plugin.bridge.let(
            data_ref.file_text,
            cb.get("data", data) or "",
        ),
    )
```

Use a less ambiguous alias when a callback argument would shadow `data`:

```python
from pyrite_sdk.api.ui import data as data_ref
```

Write a workspace file:

```python
def on_write(**_):
    plugin.file.write_file(
        "/generated.py",
        "print('hello')\n",
        callback=lambda **cb: plugin.bridge.let(data.result, str(cb)),
    )
```

Navigate between pages:

```python
Event(lambda **_: plugin.router.push("settings"))
Event(lambda **_: plugin.router.pop())
Event(lambda **_: plugin.router.goto("home"))
```

Load bundled assets:

```python
from pyrite_sdk.models.consts import PathScope

self.path.get(PathScope.ASSETS, callback=lambda **resp: self._load_assets(resp.get("path") or resp.get("data")))
```

## AI Chat Plugin Lessons

When building an OpenAI-compatible chat plugin:

- Use a settings page for URL, API key, model, TLS verification, URL auto-processing, thinking/reasoning options, and user-controlled markdown code font.
- Do not hardcode provider-specific behavior unless the user asked for it. If a field such as `reasoning_effort` is provider-specific, make it optional or configurable.
- Stream SSE carefully and show `reasoning_content` in a collapsible card when returned.
- Keep message history and send prior turns for context memory.
- If applying AI-generated diffs, use a standard unified diff parser such as `patch-ng`, validate against the current file before writing, and keep the original diff card visible after validation.
- If a request returns an HTML Cloudflare page, diagnose proxy/WAF/URL issues separately from API key or model issues.

## Pitfalls

- Do not instantiate or start the plugin during normal imports.
- Do not split a plugin into package imports unless the installed plugin layout supports those imports.
- Do not assume docs using raw `Button`, raw `onPressed`, or synchronous return values match the current SDK.
- Do not put multiple direct children in single-child widgets.
- Do not mutate `pages` without refreshing when UI structure should update.
- Do not set broad permissions by default.
- Do not assume callback payload keys; inspect wrappers and live responses.
