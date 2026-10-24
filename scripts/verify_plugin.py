#!/usr/bin/env python3
"""Verify a PyriteIDE plugin against the local pyrite-sdk before packaging.

Checks, in order of how likely they are to bite:

  1. plugin.toml parses and passes the SDK's own Manifest v2 validator.
  2. The entry contract holds: __main__.py (or .pyc), requirements.txt.
  3. Every Python file compiles.
  4. `self.<namespace>.<method>` calls exist on the SDK class.
  5. `Icons.<name>` names exist in the Material icon table.
  6. Names imported from pyrite_sdk exist.
  7. View / command ids used in code are declared in the manifest.

Usage:
    python scripts/verify_plugin.py [PLUGIN_DIR] [--strict] [--json]

PLUGIN_DIR may be the directory holding plugin.toml, or a parent that has a
single `src/` child holding it. Exit code 0 = no errors, 1 = errors found.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable

ERROR = "error"
WARN = "warn"
OK = "ok"


class Report:
    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def add(self, level: str, check: str, message: str, where: str = "") -> None:
        self.items.append(
            {"level": level, "check": check, "message": message, "where": where}
        )

    def ok(self, check: str, message: str) -> None:
        self.add(OK, check, message)

    def error(self, check: str, message: str, where: str = "") -> None:
        self.add(ERROR, check, message, where)

    def warn(self, check: str, message: str, where: str = "") -> None:
        self.add(WARN, check, message, where)

    @property
    def errors(self) -> list[dict[str, str]]:
        return [item for item in self.items if item["level"] == ERROR]

    @property
    def warnings(self) -> list[dict[str, str]]:
        return [item for item in self.items if item["level"] == WARN]

    def render(self) -> str:
        lines: list[str] = []
        for item in self.items:
            mark = {OK: "  ok  ", WARN: " warn ", ERROR: " FAIL "}[item["level"]]
            where = f"  ({item['where']})" if item["where"] else ""
            lines.append(f"[{mark}] {item['check']}: {item['message']}{where}")
        return "\n".join(lines)


def find_plugin_dir(candidate: Path) -> Path | None:
    candidate = candidate.expanduser().resolve()
    if (candidate / "plugin.toml").is_file():
        return candidate
    nested = candidate / "src"
    if (nested / "plugin.toml").is_file():
        return nested
    found = sorted(candidate.glob("*/plugin.toml"))
    if len(found) == 1:
        return found[0].parent
    return None


# --------------------------------------------------------------------------
# SDK introspection
# --------------------------------------------------------------------------


class Sdk:
    """The parts of pyrite_sdk this script needs, or None when unavailable."""

    def __init__(self) -> None:
        self.available = False
        self.reason = ""
        self.manifest_module: Any = None
        self.namespaces: dict[str, Any] = {}
        self.settings_groups: dict[str, Any] = {}
        self.icon_names: frozenset[str] = frozenset()
        self.components: frozenset[str] = frozenset()
        try:
            self._load()
            self.available = True
        except Exception as error:  # noqa: BLE001 - any import failure is fatal here
            self.reason = f"{type(error).__name__}: {error}"

    def _load(self) -> None:
        from pyrite_sdk.api.commands import Commands
        from pyrite_sdk.api.configuration import Configuration
        from pyrite_sdk.api.data import I18n, Lsp, Stubs, Theme
        from pyrite_sdk.api.dialog import Dialog
        from pyrite_sdk.api.document import EditorDocuments
        from pyrite_sdk.api.editor import Editor
        from pyrite_sdk.api.environment import Environment
        from pyrite_sdk.api.events import PluginEventBus
        from pyrite_sdk.api.file import Board, File
        from pyrite_sdk.api.icons import MATERIAL_ICON_CODES
        from pyrite_sdk.api.message import Message
        from pyrite_sdk.api.clipboard import Clipboard
        from pyrite_sdk.api.path import Path as SdkPath
        from pyrite_sdk.api.persistence import Persistence
        from pyrite_sdk.api.resources import Resources
        from pyrite_sdk.api.runtime import Runtime
        from pyrite_sdk.api.serial import Serial
        from pyrite_sdk.api.settings import Settings
        from pyrite_sdk.api.settings.settings import (
            EditorSettings,
            LspSettings,
            MicroPythonStubsSettings,
            SerialSettings,
            TerminalSettings,
            ThemeSettings,
        )
        from pyrite_sdk.api.tab import EditorTabs
        from pyrite_sdk.api.view import Views
        from pyrite_sdk.core.bridge import Bridge
        from pyrite_sdk.models import manifest as manifest_module
        from pyrite_sdk.api import components as component_module

        self.manifest_module = manifest_module
        self.namespaces = {
            "bridge": Bridge,
            "editor": Editor,
            "file": File,
            "board": Board,
            "serial": Serial,
            "persistence": Persistence,
            "settings": Settings,
            "message": Message,
            "clipboard": Clipboard,
            "dialog": Dialog,
            "resources": Resources,
            "events": PluginEventBus,
            "commands": Commands,
            "configuration": Configuration,
            "documents": EditorDocuments,
            "runtime": Runtime,
            "editor_tabs": EditorTabs,
            "views": Views,
            "theme": Theme,
            "i18n": I18n,
            "stubs": Stubs,
            "lsp": Lsp,
            "path": SdkPath,
            "env": Environment,
        }
        self.settings_groups = {
            "theme": ThemeSettings,
            "editor": EditorSettings,
            "lsp": LspSettings,
            "serial": SerialSettings,
            "terminal": TerminalSettings,
            "micropython_stubs": MicroPythonStubsSettings,
        }
        self.icon_names = frozenset(MATERIAL_ICON_CODES)
        self.components = frozenset(
            name
            for name in dir(component_module)
            if not name.startswith("_") and name[0].isupper()
        )


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check_manifest(plugin_dir: Path, sdk: Sdk, report: Report) -> tuple[Any, dict[str, Any]]:
    manifest_path = plugin_dir / "plugin.toml"
    raw: dict[str, Any] = {}
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        report.error("manifest", f"cannot read plugin.toml: {error}")
        return None, raw

    if not sdk.available:
        report.warn(
            "manifest",
            "pyrite-sdk is not importable, only TOML syntax was checked "
            f"({sdk.reason})",
        )
        return None, raw

    try:
        manifest = sdk.manifest_module.load_file(manifest_path)
    except Exception as error:  # noqa: BLE001 - ManifestValidationError
        code = getattr(error, "code", "manifest_invalid")
        message = getattr(error, "message", str(error))
        report.error("manifest", f"{code}: {message}")
        return None, raw

    report.ok(
        "manifest",
        f"{manifest.type} plugin '{manifest.id}' v{manifest.version} "
        f"({len(manifest.contributes.views)} views, "
        f"{len(manifest.contributes.commands)} commands, "
        f"{len(manifest.contributes.configuration)} settings)",
    )
    return manifest, raw


def declared_ids(
    manifest: Any, raw: dict[str, Any]
) -> tuple[set[str], set[str], set[str]] | None:
    """View / command / configuration ids, from the model or from raw TOML."""
    if manifest is not None and hasattr(manifest, "contributes"):
        contributes = manifest.contributes
        return (
            {view.id for view in contributes.views},
            {command.id for command in contributes.commands},
            {item.id for item in contributes.configuration},
        )
    contributes = raw.get("contributes")
    if not isinstance(contributes, dict):
        return None

    def ids(key: str) -> set[str]:
        entries = contributes.get(key)
        if not isinstance(entries, list):
            return set()
        return {
            str(entry["id"])
            for entry in entries
            if isinstance(entry, dict) and "id" in entry
        }

    return ids("views"), ids("commands"), ids("configuration")


def check_entry(plugin_dir: Path, report: Report) -> None:
    entry = plugin_dir / "__main__.py"
    compiled = plugin_dir / "__main__.pyc"
    if entry.is_file():
        report.ok("entry", "__main__.py present")
    elif compiled.is_file():
        report.warn("entry", "only __main__.pyc present; the host can run it, "
                             "but keep the source in version control")
    else:
        report.error("entry", "missing __main__.py (the packager requires it)")
    if not (plugin_dir / "requirements.txt").is_file():
        report.warn("entry", "no requirements.txt; `pyrsdk package` will skip "
                             "dependency installation")


def python_files(plugin_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(plugin_dir.rglob("*.py")):
        rel = path.relative_to(plugin_dir)
        if any(part in {".venv", "build", "dist", "__pycache__"} for part in rel.parts):
            continue
        files.append(path)
    return files


def check_syntax(files: Iterable[Path], plugin_dir: Path, report: Report) -> dict[Path, ast.Module]:
    trees: dict[Path, ast.Module] = {}
    failures = 0
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            trees[path] = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            line = getattr(error, "lineno", None)
            where = f"{path.relative_to(plugin_dir)}:{line}" if line else str(path)
            report.error("syntax", str(error), where)
            failures += 1
    if not failures and trees:
        report.ok("syntax", f"{len(trees)} file(s) parse")
    return trees


def _line(node: ast.AST) -> int:
    return getattr(node, "lineno", 0)


def check_self_calls(
    trees: dict[Path, ast.Module], plugin_dir: Path, sdk: Sdk, report: Report
) -> None:
    if not sdk.available:
        return
    problems = 0
    for path, tree in trees.items():
        rel = path.relative_to(plugin_dir)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            # self.<ns>.<method>
            owner = node.value
            if (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
            ):
                target = sdk.namespaces.get(owner.attr)
                if target is not None:
                    # Settings groups live on the instance, not the class.
                    if owner.attr == "settings" and node.attr in sdk.settings_groups:
                        continue
                    problems += _check_member(
                        report, rel, node, target,
                        f"self.{owner.attr}.{node.attr}",
                    )
                    continue
            # self.settings.<group>.<method>
            if (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Attribute)
                and isinstance(owner.value.value, ast.Name)
                and owner.value.value.id == "self"
                and owner.value.attr == "settings"
            ):
                target = sdk.settings_groups.get(owner.attr)
                if target is not None:
                    problems += _check_member(
                        report, rel, node, target,
                        f"self.settings.{owner.attr}.{node.attr}",
                    )
    if problems == 0:
        report.ok("api", "every self.<namespace>.<method> resolves")


def _check_member(
    report: Report, rel: Path, node: ast.Attribute, target: Any, label: str
) -> int:
    members = {name for name in dir(target) if not name.startswith("_")}
    if node.attr in members:
        return 0
    hint = difflib.get_close_matches(node.attr, sorted(members), n=1)
    suggestion = f"; did you mean '{hint[0]}'?" if hint else ""
    report.error("api", f"{label} does not exist{suggestion}", f"{rel}:{_line(node)}")
    return 1


def check_icons(
    trees: dict[Path, ast.Module], plugin_dir: Path, sdk: Sdk, report: Report
) -> None:
    if not sdk.available:
        return
    problems = 0
    for path, tree in trees.items():
        rel = path.relative_to(plugin_dir)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if not isinstance(node.value, ast.Name) or node.value.id != "Icons":
                continue
            if node.attr in sdk.icon_names:
                continue
            hint = difflib.get_close_matches(node.attr, sorted(sdk.icon_names), n=1)
            suggestion = f"; did you mean 'Icons.{hint[0]}'?" if hint else ""
            report.error(
                "icons", f"Icons.{node.attr} is not a Material icon{suggestion}",
                f"{rel}:{_line(node)}",
            )
            problems += 1
    if problems == 0:
        report.ok("icons", "every Icons.<name> exists")


def check_sdk_imports(
    trees: dict[Path, ast.Module], plugin_dir: Path, sdk: Sdk, report: Report
) -> None:
    if not sdk.available:
        return
    problems = 0
    for path, tree in trees.items():
        rel = path.relative_to(plugin_dir)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith("pyrite_sdk"):
                continue
            try:
                module = __import__(node.module, fromlist=["*"])
            except Exception as error:  # noqa: BLE001
                report.error(
                    "imports", f"cannot import {node.module}: {error}",
                    f"{rel}:{_line(node)}",
                )
                problems += 1
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                if hasattr(module, alias.name):
                    continue
                hint = difflib.get_close_matches(
                    alias.name, [n for n in dir(module) if not n.startswith("_")], n=1
                )
                suggestion = f"; did you mean '{hint[0]}'?" if hint else ""
                report.error(
                    "imports",
                    f"{node.module} has no '{alias.name}'{suggestion}",
                    f"{rel}:{_line(node)}",
                )
                problems += 1
    if problems == 0:
        report.ok("imports", "every pyrite_sdk import resolves")


VIEW_FACADES = {
    "create",
    "open",
    "outline",
    "tree",
    "virtual_list",
    "table",
    "form",
    "markdown",
    "log",
    "variable_inspector",
}


#: namespace -> (read permission, write permission). None means "not gated".
PERMISSION_MAP: dict[str, tuple[str | None, str | None]] = {
    "editor": ("editor.read", "editor.write"),
    "documents": ("editor.read", "editor.write"),
    "file": ("file.read", "file.write"),
    "board": ("board.read", "board.write"),
    "serial": ("serial.read", "serial.write"),
    "persistence": ("persistence.read", "persistence.write"),
    "settings": ("settings.read", "settings.write"),
    "theme": ("data.read", "data.write"),
    "i18n": ("data.read", "data.write"),
    "stubs": ("data.read", "data.write"),
    "lsp": ("data.read", "data.write"),
    "runtime": ("runtime.inspect", None),
    "message": ("ui.notify", None),
    "clipboard": ("ui.view", None),
    "dialog": ("dialog.show", None),
    "editor_tabs": ("tab.manage", None),
}

READ_PREFIXES = (
    "get_",
    "is_",
    "list",
    "can_",
    "exists",
    "find",
    "read_",
    "resolve_",
)
READ_NAMES = {"copy", "clear_search", "sessions", "state", "scopes", "variables",
              "children", "object_info", "symbols"}


def is_read_call(method: str) -> bool:
    return method in READ_NAMES or method.startswith(READ_PREFIXES)


def is_subscription(method: str) -> bool:
    """on_* / off_* register a local handler; the host gates the topic, not the call."""
    return method.startswith(("on_", "off_"))


def declared_permissions(manifest: Any, raw: dict[str, Any]) -> set[str] | None:
    if manifest is not None and hasattr(manifest, "permissions"):
        return {str(item) for item in manifest.permissions}
    permissions = raw.get("permissions")
    if isinstance(permissions, list):
        return {str(item) for item in permissions}
    return None


def check_permissions(
    trees: dict[Path, ast.Module],
    plugin_dir: Path,
    permissions: set[str] | None,
    sdk: Sdk,
    report: Report,
) -> None:
    """Warn when the code calls something whose permission is not declared."""
    if permissions is None or not sdk.available:
        return
    missing: dict[str, set[str]] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            owner = func.value
            if not (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
            ):
                continue
            spec = PERMISSION_MAP.get(owner.attr)
            if spec is None or is_subscription(func.attr):
                continue
            read_perm, write_perm = spec
            needed = read_perm if is_read_call(func.attr) else write_perm
            if needed and needed not in permissions:
                missing.setdefault(needed, set()).add(
                    f"{owner.attr}.{func.attr}"
                )
    if not missing:
        report.ok("permissions", "declared permissions cover the calls used")
        return
    for permission, uses in sorted(missing.items()):
        sample = ", ".join(sorted(uses)[:4])
        more = "" if len(uses) <= 4 else f" (+{len(uses) - 4} more)"
        report.warn(
            "permissions",
            f"{permission} is not declared but needed by {sample}{more}",
        )


def check_contribution_ids(
    trees: dict[Path, ast.Module],
    plugin_dir: Path,
    ids: tuple[set[str], set[str], set[str]] | None,
    report: Report,
) -> None:
    if ids is None:
        return
    views, commands, settings = ids
    problems = 0

    for path, tree in trees.items():
        rel = path.relative_to(plugin_dir)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Attribute):
                continue
            if not isinstance(func.value.value, ast.Name) or func.value.value.id != "self":
                continue
            namespace, method = func.value.attr, func.attr
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            value = first.value

            if namespace == "views" and method in VIEW_FACADES and value not in views:
                report.error(
                    "ids",
                    f"view id '{value}' is not declared in plugin.toml",
                    f"{rel}:{_line(node)}",
                )
                problems += 1
            elif namespace == "commands" and method == "register" and value not in commands:
                report.error(
                    "ids",
                    f"command id '{value}' is not declared in plugin.toml",
                    f"{rel}:{_line(node)}",
                )
                problems += 1
            elif (
                namespace == "configuration"
                and method in {"get", "set"}
                and value not in settings
            ):
                report.warn(
                    "ids",
                    f"configuration id '{value}' is not declared in plugin.toml",
                    f"{rel}:{_line(node)}",
                )
    if problems == 0:
        report.ok("ids", "view and command ids match the manifest")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def verify(plugin_dir: Path) -> Report:
    report = Report()
    sdk = Sdk()
    if not sdk.available:
        report.warn("sdk", f"deep checks disabled ({sdk.reason})")

    manifest, raw = check_manifest(plugin_dir, sdk, report)
    check_entry(plugin_dir, report)
    trees = check_syntax(python_files(plugin_dir), plugin_dir, report)
    check_self_calls(trees, plugin_dir, sdk, report)
    check_icons(trees, plugin_dir, sdk, report)
    check_sdk_imports(trees, plugin_dir, sdk, report)
    check_permissions(
        trees, plugin_dir, declared_permissions(manifest, raw), sdk, report
    )
    check_contribution_ids(
        trees, plugin_dir, declared_ids(manifest, raw), report
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plugin_dir", nargs="?", default=".",
                        help="plugin directory (or a parent containing src/)")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    plugin_dir = find_plugin_dir(Path(args.plugin_dir))
    if plugin_dir is None:
        print(f"no plugin.toml found under {Path(args.plugin_dir).resolve()}")
        return 1

    report = verify(plugin_dir)
    failed = bool(report.errors) or (args.strict and bool(report.warnings))

    if args.json:
        print(json.dumps(
            {
                "plugin_dir": str(plugin_dir),
                "ok": not failed,
                "items": report.items,
            },
            indent=2,
        ))
    else:
        print(f"plugin: {plugin_dir}")
        print(report.render())
        print()
        print(
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
