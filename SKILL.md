---
name: pyrite-ide-plugin-creator
description: "Create, modify, debug, package, and validate PyriteIDE plugins built with PyriteSDK in Python. Use when needs to scaffold or edit Pyrite plugins, plugin.toml manifests, UiPlugin/ServicePlugin/DataPlugin code, RFW UI pages, plugin settings, persistence, file/board/editor/serial APIs, markdown widgets, assets_path usage, permissions, or pyrsdk packaging."
---

# Pyrite IDE Plugin Creator

Use this skill to build PyriteIDE plugins with PyriteSDK. Treat the SDK repo and PyriteIDE host source as the source of truth; this stack changes quickly, and some docs or old examples use stale API shapes.

## Workflow

1. Prepare an environment (See in the `## Environment`).
2. Read only the needed reference:
   - Read `references/sdk-reference.md` for verified source paths, runtime behavior, permissions, validation, and packaging.
   - Read `references/plugin-patterns.md` when creating or heavily restructuring a plugin.
   - Inspect current source and examples before relying on docs: `src/pyrite_sdk`, `examples/*_plugin`, `tests/test_ui_api.py`, and when host behavior matters, the PyriteIDE RFW widget bridge/tests.
3. Classify the plugin:
   - Use `UiPlugin` for pages, controls, chat tools, editor/file actions, and RFW events.
   - Use `ServicePlugin` for background work without pages.
   - Use `DataPlugin` for theme, i18n, stubs, and one-shot contributions.
4. Align `plugin.toml` with the code. Add only permissions the plugin actually uses; verify uncertain permissions against `docs/api.md` or host permission code.
5. Implement in Python SDK style:
   - Use snake_case names exactly as exposed by the SDK, such as `Alignment.top_center`, not Dart-style names.
   - Use `Event(callback, args={...})` for callbacks and accept `**kwargs`.
   - Use `plugin.bridge.let(data.some_key, value)` for dynamic UI values; rebuild `self.pages[...]` and call `self.bridge.refresh(call_on_refresh=False)` when page structure changes.
   - Put `plugin.start()` or `plugin.run_once()` inside `main()` so imports and tests stay safe.
6. Validate locally. Do not call `plugin.start()` outside PyriteIDE unless the required bridge environment is set.
7. Package with `pyrsdk [/path/to/plugin] -p [Platform] (-r "--find-links=/path/to/dir")` explicitly does not need it

## Environment

To prepare an environment:

```bash
python path/to/pyrite-plugin-creator/scripts/init_environment.py --output ./my-plugin
```

Useful option:
- `--find_links /path/to/dir` to install `pyrite-sdk` with whl instead of PyPI. (is `--find_links`, not `--find-links`)

## Scaffolding

For a new plugin, prefer the bundled scaffolder, then edit the generated files:

```bash
python path/to/pyrite-plugin-creator/scripts/scaffold_pyrite_plugin.py \
  --output ./my-plugin \
  --id my-plugin \
  --name "My Plugin" \
  --type ui \
  --author "Your Name"
```

Useful options:

- `--type ui|service|data|theme|i18n|stubs`
- `--permission file --permission editor` to add permissions
- `--platform linux --platform macos` to restrict platforms
- `--sdk-requirement pyrite-sdk==0.0.0` to control `requirements.txt`
- `--force` to overwrite generated files

## UI Guardrails

- Build actual plugin pages, not landing pages.
- Prefer compact, native-feeling layouts with `Padding`, `margin`, `Card`, `Column`, and `Row`; avoid spacer-only `SizedBox` unless source examples prove it is needed.
- Remember RFW single-child widgets: `Padding`, `Container`, `Expanded`, `SafeArea`, `Center`, `Align`, and button widgets can only receive one direct child. Wrap multiple children in `Column`, `Row`, or another multi-child widget.
- Use Python SDK wrappers, not raw Flutter/Dart assumptions. If an attribute fails, inspect `/path/to/venv-libs/pyrite_sdk/api/ui/sentence/expression.py` or the widget wrapper.

## Notice
- Minimize or avoid using custom parsers as a replacement for the SDK's exposed configuration options unless necessary.
- Never modify any source code of the SDK.

## Validation

Use focused checks before handing work back:

```bash
.venv/bin/python -m py_compile /path/to/plugin/__main__.py
.venv/bin/python -m unittest tests.test_ui_api
python - <<'PY'
import pathlib, tomllib
print(tomllib.loads(pathlib.Path("/path/to/plugin/plugin.toml").read_text()))
PY
```

If the plugin has UI pages and the entrypoint is import-safe, also serialize pages with `page.to_rfw()` or a small smoke test. When SDK/IDE host widgets are changed, also run the matching Flutter widget test in the PyriteIDE repo.
k lambdas are evaluated when building the page; ensure constants are in scope and defaults are literal-safe.
- `Too many child in XXX`: a single-child widget received multiple direct children. Wrap the generated content in a `Column` or `Row`.
- `Expected state but found data`: do not emit raw `set data...` statements in RFW; update data from Python with `plugin.bridge.let(...)`.
- UI state does not refresh: rebuild the page and call `self.bridge.refresh(call_on_refresh=False)`.
- Callback data is missing or shaped differently: inspect the wrapper and live `**kwargs`; many APIs return values under `data`, `path`, `content`, or error keys depending on the handler.
- API request returns an HTML Cloudflare page: the request likely never reached the API; diagnose URL and proxy/WAF rules separately from plugin code.
