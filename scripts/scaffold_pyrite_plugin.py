#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from textwrap import dedent


PLUGIN_TYPES = ("ui", "service", "data", "theme", "i18n", "stubs")
PERMISSIONS = ("ui", "file", "board", "editor", "settings", "serial", "persistence", "data")
PLATFORMS = ("linux", "macos", "windows", "android")

DEFAULT_PERMISSIONS = {
    "ui": ("ui",),
    "service": (),
    "data": ("data",),
    "theme": ("data",),
    "i18n": ("data",),
    "stubs": ("data", "settings"),
}

TOML_TYPES = {
    "ui": "ui",
    "service": "service",
    "data": "data",
    "theme": "data",
    "i18n": "data",
    "stubs": "data",
}


def normalize_id(value: str) -> str:
    plugin_id = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    if not plugin_id:
        raise ValueError("plugin id must contain at least one letter or digit")
    return plugin_id


def class_name_from(plugin_id: str) -> str:
    parts = re.split(r"[-_]+", plugin_id)
    name = "".join(part[:1].upper() + part[1:] for part in parts if part)
    if not name:
        name = "Pyrite"
    if name[0].isdigit():
        name = "Pyrite" + name
    if not name.endswith("Plugin"):
        name += "Plugin"
    return name


def ordered(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for candidate in (*PERMISSIONS, *PLATFORMS):
        if candidate in values and candidate not in result:
            result.append(candidate)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def toml_bool_table(title: str, keys: list[str]) -> str:
    lines = [f"[{title}]"]
    lines.extend(f"{key} = true" for key in keys)
    return "\n".join(lines)


def build_plugin_toml(args: argparse.Namespace, permissions: list[str], platforms: list[str]) -> str:
    general = [
        "[general]",
        f'name = "{args.name}"',
        f'id = "{args.plugin_id}"',
        f'version = "{args.version}"',
        f'author = "{args.author}"',
        f'type = "{TOML_TYPES[args.kind]}"',
    ]
    if args.kind == "service" and args.auto_start:
        general.append("auto_start = true")
    return "\n\n".join(
        [
            "\n".join(general),
            toml_bool_table("permissions", permissions),
            toml_bool_table("platform", platforms),
            "",
        ]
    )


def ui_template(class_name: str, display_name: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.api.ui.event import Event
        from pyrite_sdk.api.ui.page import Page
        from pyrite_sdk.api.ui.sentence import *
        from pyrite_sdk.api.ui.widgets import *
        from pyrite_sdk.core.plugin import UiPlugin
        from pyrite_sdk.models.consts import Package, Ui


        def build_home_page(plugin: UiPlugin, status: str):
            page = Page([Package.core.widgets, Package.core.material])
            root = NewWidget(Ui.root).add_to(page)
            with Scaffold(app_bar=AppBar(title=Text("{display_name}"))).add_to(root)\\
                .add(Padding(EdgeInsets.all(12)))\\
                .add(Column(cross_axis_alignment=CrossAxisAlignment.stretch)):
                Text("{display_name}", style=TextStyle(font_size=20, font_weight=FontWeight.bold))
                Padding(EdgeInsets.only(top=8)).add(Text(["Status: ", status]))
                Padding(EdgeInsets.only(top=12))
                with Row(cross_axis_alignment=CrossAxisAlignment.center):
                    ElevatedButton(Event(lambda **_: plugin.set_status("Clicked"))).add_to(Expanded()).add(Text("Run"))
            return page


        class {class_name}(UiPlugin):
            def __init__(self):
                super().__init__()
                self.status = "Ready"
                self.pages = {{}}
                self._render()

            def on_start(self):
                print("{display_name} started")
                self.router.goto("home")

            def on_refresh(self):
                self._render()

            def _render(self):
                self.pages = {{"home": build_home_page(self, self.status)}}

            def set_status(self, value: str):
                self.status = value
                self._render()
                self.bridge.refresh(call_on_refresh=False)

            def on_dispose(self):
                print("{display_name} disposed")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.start()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def service_template(class_name: str, display_name: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.core.plugin import ServicePlugin


        class {class_name}(ServicePlugin):
            def __init__(self):
                super().__init__()
                self.running = False

            def on_start(self):
                self.running = True
                print("{display_name} started")

            def on_pause(self):
                print("{display_name} paused")

            def on_resume(self):
                print("{display_name} resumed")

            def on_dispose(self):
                self.running = False
                print("{display_name} disposed")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.start()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def data_template(class_name: str, display_name: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.core.plugin import DataPlugin


        class {class_name}(DataPlugin):
            def on_contribute(self):
                print("{display_name} has no contributions yet")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.run_once()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def theme_template(class_name: str, display_name: str, plugin_id: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.core.plugin import DataPlugin


        class {class_name}(DataPlugin):
            def on_contribute(self):
                self.theme.contribute(
                    "{plugin_id}",
                    {{
                        "color.primary": "#5E81AC",
                        "color.onPrimary": "#FFFFFF",
                        "color.surface": "#FFFFFF",
                        "color.onSurface": "#111111",
                        "dark.color.primary": "#88C0D0",
                        "dark.color.onPrimary": "#111111",
                    }},
                )
                print("{display_name} contributed theme data")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.run_once()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def i18n_template(class_name: str, display_name: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.core.plugin import DataPlugin


        class {class_name}(DataPlugin):
            def on_contribute(self):
                self.i18n.contribute("en", {{"plugin.sample": "{display_name}"}})
                self.i18n.contribute("zh-CN", {{"plugin.sample": "{display_name}"}})
                print("{display_name} contributed i18n data")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.run_once()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def stubs_template(class_name: str, display_name: str, plugin_id: str) -> str:
    return dedent(
        f'''
        from pyrite_sdk.core.plugin import DataPlugin


        class {class_name}(DataPlugin):
            def on_contribute(self):
                root = self.path.plugin() / "stubs"
                self.stubs.contribute(
                    provider_id="{plugin_id}",
                    kind="micropython",
                    version="0.1.0",
                    profiles=[
                        {{
                            "id": "generic",
                            "label": "{display_name} Generic",
                            "path": str(root / "generic"),
                            "priority": 10,
                        }}
                    ],
                    aliases=["micropython"],
                )
                print("{display_name} contributed stubs")


        plugin = None


        def main():
            global plugin
            plugin = {class_name}()
            plugin.run_once()

        if __name__ == "__main__":
            main()
        '''
    ).lstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a minimal PyriteSDK plugin scaffold.")
    parser.add_argument("--output", "-o", required=True, help="Plugin output directory.")
    parser.add_argument("--id", dest="plugin_id", required=True, help="Plugin id, normalized to lower hyphen-case.")
    parser.add_argument("--name", required=True, help="Human-facing plugin name.")
    parser.add_argument("--type", dest="kind", choices=PLUGIN_TYPES, default="ui", help="Plugin scaffold type.")
    parser.add_argument("--author", default="Pyrite Plugin Developer", help="plugin.toml author.")
    parser.add_argument("--version", default="0.1.0", help="plugin.toml version.")
    parser.add_argument("--permission", action="append", choices=PERMISSIONS, help="Permission to add; repeatable.")
    parser.add_argument("--platform", action="append", choices=PLATFORMS, help="Platform to enable; repeatable.")
    parser.add_argument("--sdk-requirement", default="pyrite-sdk==0.0.0", help="Line to write to requirements.txt.")
    parser.add_argument("--auto-start", action="store_true", help="Add auto_start = true for service plugins.")
    parser.add_argument("--force", action="store_true", help="Overwrite generated files if they exist.")
    args = parser.parse_args()

    try:
        args.plugin_id = normalize_id(args.plugin_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.output).expanduser().resolve()
    class_name = class_name_from(args.plugin_id)
    permissions = ordered([*DEFAULT_PERMISSIONS[args.kind], *(args.permission or [])])
    platforms = ordered(args.platform or PLATFORMS)

    templates = {
        "ui": ui_template,
        "service": service_template,
        "data": data_template,
        "theme": theme_template,
        "i18n": i18n_template,
        "stubs": stubs_template,
    }

    main_builder = templates[args.kind]
    if args.kind in {"theme", "stubs"}:
        main_py = main_builder(class_name, args.name, args.plugin_id)
    else:
        main_py = main_builder(class_name, args.name)

    files = {
        "plugin.toml": build_plugin_toml(args, permissions, platforms),
        "__main__.py": main_py,
        "requirements.txt": (args.sdk_requirement.strip() + "\n") if args.sdk_requirement.strip() else "",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = out_dir / relative
        if target.exists() and not args.force:
            print(f"error: {target} already exists; use --force to overwrite", file=sys.stderr)
            return 3
        target.write_text(content, encoding="utf-8")

    if args.kind == "stubs":
        stub_dir = out_dir / "stubs" / "generic"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "example.pyi").write_text("# Add MicroPython stubs here.\n", encoding="utf-8")

    print(f"created {args.kind} plugin scaffold at {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
