---
name: pyrite-ide-plugin-creator
description: Create, modify, debug, package, and validate third-party PyriteIDE plugins in Python with pyrite-sdk package. Use only for plugin work involving plugin.toml Manifest v2, UiPlugin/ServicePlugin/DataPlugin lifecycles, native views and component UI, commands, configuration, events, persistence, editor/file/board/serial/runtime APIs, resources, permissions, or pyrsdk tooling. Do not use when changing the PyriteSDK package itself or the PyriteIDE host/runtime implementation.
---

# PyriteIDE Plugin Creator

Build plugins against the public `pyrite-sdk` 1.x contract. Keep every change inside the plugin project. Use the bundled references as the working API guide and never handcraft the private transport protocol.

## Workflow

1. Inspect the target plugin before editing. Read `plugin.toml`, the Python entrypoint, requirements, assets, tests, and the current Git diff.
2. Install the SDK from PyPI when the environment is missing. Use `scripts/init_environment.py` to create a virtual environment with `pyrite-sdk` installed. Activate the environment before editing or testing.
3. Classify the plugin:
   - Use `UiPlugin` for contributed views, tabs, interactive components, editor tools, or visible commands.
   - Use `ServicePlugin` for host-activated background behavior without contributed UI.
   - Use `DataPlugin` for one-shot theme, localization, or stubs contributions.
4. Read the references required by the task:
   - `references/manifest-v2.md`: read whenever creating or changing `plugin.toml`, contributions, permissions, activation, icons, platforms, or `when` expressions.
   - `references/communication-lifecycle.md`: read for startup, callbacks, async handlers, context, disposal, transport failures, or reconnect behavior.
   - `references/ui-views.md`: read for any contributed view, typed native renderer, snapshot, patch, visibility, routing, tab instance, or context-menu behavior.
   - `references/ui-components.md`: read before using component trees, component events/controllers, menus, media, data components, or Canvas.
   - `references/ui-examples.md`: read when implementing UI. Keep UI examples out of this file.
   - `references/sdk-operations.md`: read before calling an SDK namespace or choosing a permission. It lists every public operation and every typed settings group.
   - `references/plugin-patterns.md`: read for service/data skeletons, command registration, subscriptions, persistence, and import-safe entrypoints.
5. Align code and Manifest v2. Declare every view, command, configuration key, activation event, and platform used by the plugin. Add only the narrow read/write permissions required by actual calls.
6. Use SDK objects rather than protocol dictionaries:
   - Create views through `plugin.views` and UI through `pyrite_sdk.api.components` or typed renderer facades.
   - Use `plugin.commands`, `plugin.configuration`, and `plugin.events` for host interaction.
   - Use `plugin.resources.asset("assets/...")` for image, video, and Canvas resources.
   - Use `Icons.<name>` for Material icons.
7. Keep execution import-safe. Put `plugin.start()` or `plugin.run_once()` behind `if __name__ == "__main__":`. Do not start a bridge during ordinary imports or unit tests.
8. Validate in increasing scope:
   - Parse `plugin.toml` and run `pyrsdk test <plugin-dir>`.
   - Compile the Python entrypoint and run focused plugin tests.
   - Exercise changed callbacks, commands, configuration, and view updates in PyriteIDE when available.
   - Package each requested target with `pyrsdk package` and inspect the produced archive contents and hash.

## Non-Negotiable Contracts

- Require Manifest v2: explicit `manifest_version = 2` and `protocol_version = 1`.
- Do not use legacy `[general]`, `[permissions]`, or `[platform]` tables.
- Do not use RFW pages, routers, events, refresh calls, or RFW test flags. UI is a native view model containing typed renderer data or component trees.
- Do not create WebSocket/TCP clients, read bridge ports, send envelopes, or implement a handshake. The host injects and owns the native transport.
- Treat callbacks as asynchronous host responses. Accept `error` and flexible response fields; do not assume every API returns one fixed `data` key.
- Give every event-producing or controller-driven component a stable, unique `id` within its view instance.
- Send a complete snapshot before relying on incremental patches. Preserve stable node IDs across updates.
- Recreate runtime object references after a backend restart; old references are stale by design.
- Never broaden permissions to hide an API or configuration error.

## Scaffolding

For a new plugin, generate a Manifest v2 project and then adapt the result:

```bash
python path/to/skill/scripts/scaffold_pyrite_plugin.py --output ./my-plugin --id acme.my-plugin --name "My Plugin" --type ui --author "Acme"
```

Useful options include `--type ui|service|data|theme|i18n|stubs`, `--renderer`, repeatable `--permission`, repeatable `--platform`, repeatable `--activation-event`, `--python-version`, `--sdk-requirement`, and `--force`.

## Validation Commands

Use commands appropriate to the plugin and operating system:

```bash
python -m py_compile path/to/plugin/__main__.py
python -c "import pathlib,tomllib; tomllib.loads(pathlib.Path('path/to/plugin/plugin.toml').read_text(encoding='utf-8'))"
pyrsdk test path/to/plugin
pyrsdk package path/to/plugin -p Windows
```

Report focused checks separately from packaging and live-host validation. If PyriteIDE is unavailable, state that native rendering, permission prompts, and host callbacks were not exercised.
