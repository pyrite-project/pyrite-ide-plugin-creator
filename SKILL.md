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

## Coding

Apply these rules when inspecting, creating, modifying, debugging, or validating a PyriteIDE plugin.

### Understand Before Editing

- Treat the user's request, the current workspace, and the existing implementation as the task context. When asked to change code, locate and modify the real code instead of replying with an isolated example.
- Read every target file before editing it. Trace relevant call sites, wrappers, tests, configuration, and similar implementations before proposing a change.
- Search before claiming that a file, symbol, API, or capability is missing. Start broad when its location is unknown, then narrow to the relevant code path.
- Use PyriteSDK source, current examples, tests, and the PyriteIDE host bridge as the source of truth. Do not substitute generic Flutter, Dart, or Python assumptions for the serialized API that the bridge actually supports.
- Inspect `git status` and the relevant diff before changing a dirty workspace. Preserve user changes and unrelated work; never overwrite or revert changes merely because they are outside the current task.
- If the request appears to rely on a misconception or conflicts with current runtime behavior, explain the issue briefly and follow the verified implementation rather than silently encoding a false assumption.

### Scope and Design

- Implement the complete requested behavior without adding unrelated features, cleanup, configurability, or refactors.
- Follow existing repository patterns, naming, ownership boundaries, and helper APIs. Prefer a nearby working example over a newly invented structure.
- Keep complexity proportional to the task. Do not create one-use helpers, speculative extension points, feature flags, compatibility shims, or abstractions for hypothetical future needs.
- Prefer a few clear repeated lines over a premature abstraction. Add an abstraction only when it removes meaningful duplication or matches an established local pattern.
- Validate at real boundaries such as user input, plugin configuration, files, serial devices, bridge payloads, and external APIs. Do not add defensive branches for states already excluded by internal contracts.
- Prefer editing an existing file to creating a new one. Create files only when the requested artifact or repository structure genuinely requires them; never add unsolicited README or auxiliary documentation files.
- Keep `plugin.toml`, Python entrypoints, permissions, platform restrictions, requirements, docs, examples, and tests consistent with the behavior being implemented.
- Add only permissions the plugin actually uses. Never broaden permissions as a shortcut around an API or configuration problem.
- Never modify PyriteSDK or PyriteIDE source merely to make a generated plugin work unless the user explicitly requests a host or SDK change. Fix the plugin against the supported contract.

### Implementation Discipline

- Use the SDK's exact Python-facing names and payload shapes. Preserve snake_case APIs, `Event(callback, args={...})`, callback `**kwargs`, `plugin.bridge.let(...)`, page rebuilding, and refresh semantics where applicable.
- Prefer structured APIs and parsers over ad hoc string manipulation, especially for TOML, JSON, paths, manifests, and serialized widget data.
- Reuse existing utilities for path handling, configuration, state, serialization, and environment checks. Before adding inline logic, search for an established helper.
- Keep comments rare. Add one only to explain a non-obvious constraint, invariant, workaround, or surprising behavior; do not narrate what well-named code already says.
- Preserve existing comments unless the described code is removed or the comment is demonstrably incorrect. An unusual comment may encode a hidden compatibility constraint.
- Do not add task-history comments such as "added for this fix" or "used by this flow"; put transient reasoning in the final report, not in source code.
- Avoid security defects such as command injection, unsafe path construction, secret exposure, unvalidated external content, and overly broad file or serial access. Correct any security issue introduced by the change before finishing.
- Keep imports and module execution safe. Put `plugin.start()` or `plugin.run_once()` inside `main()` and avoid import-time side effects that break tests or tooling.
- For UI changes, respect single-child widget constraints and the actual RFW nesting/data-key behavior. Do not assume a widget property serialized successfully until its emitted payload or rendered behavior is checked.

### Execution and Tool Use

- For a straightforward task, act directly. For a multi-step task, maintain a short actionable plan and keep only one dependent step in progress at a time.
- Run independent reads, searches, and checks in parallel when they cannot affect one another. Run dependent or state-changing operations sequentially.
- Prefer dedicated file and search tools when available. Use shell commands for test runners, builds, package operations, git inspection, and other operations that genuinely require a shell.
- Use focused searches and targeted reads instead of repeatedly loading entire large files. Use symbol/reference tooling when available to trace definitions and call sites.
- When an approach fails, read the exact error, check assumptions, identify the root cause, and apply a focused fix. Do not repeat the identical failing action blindly or switch approaches without understanding the failure.
- Do not suppress errors, discard stderr, weaken tests, or add `|| true` merely to obtain a successful-looking result.
- Do not install dependencies, change global configuration, or alter the environment unless the task requires it. Prefer the repository's existing environment and declared toolchain.
- Use temporary locations for disposable probes and generated scratch data. Do not leave debugging artifacts, caches, or throwaway scripts in the plugin workspace.

### Workspace and Git Safety

- Treat local edits and test execution as reversible actions. Before destructive, shared, or hard-to-reverse actions, verify that the user explicitly requested them and that the scope is clear.
- Never use destructive git commands such as `reset --hard`, `clean -f`, force push, broad restore/checkout, or branch deletion as a shortcut around unexpected state.
- Never change git configuration, skip hooks, bypass signing, or amend an existing commit unless the user explicitly requests that exact action.
- Do not commit, push, create a branch, or open a pull request unless requested. Approval for one git action does not imply approval for later actions.
- When staging is requested, stage named files rather than the whole workspace so unrelated changes, secrets, and generated artifacts are not included accidentally.
- Investigate unfamiliar files, lock files, merge conflicts, generated output, and failing hooks before deleting, overwriting, or bypassing them.

### Verification

- Verification means executing the changed behavior, not only reading the code. Before reporting completion, run the most relevant checks available and inspect their actual output.
- For bug fixes, reproduce the original failure when practical, apply the fix, rerun the reproduction, then run focused regression tests.
- For plugin entrypoints and scripts, compile or import them, run representative inputs, and check stdout, stderr, exceptions, and exit behavior where relevant.
- For manifests and configuration, parse them with the real parser and verify that IDs, plugin type, entrypoint, permissions, platforms, and dependencies agree with the code.
- For UI plugins, serialize pages with `to_rfw()` or a focused smoke test when import-safe. Check event payloads, dynamic data keys, refresh behavior, and single-child structure; use host-side tests or rendered inspection when the bridge is involved.
- For service, file, editor, board, serial, or external API behavior, exercise the public operation with representative data and verify response values or side effects, not only a successful status.
- Test at least one relevant edge or failure case such as empty input, malformed configuration, missing data, repeated calls, invalid paths, callback errors, or boundary values.
- Run the narrowest useful checks first, then broaden according to risk: syntax/compile, focused unit tests, related suite, lint/type checks, package/build checks, and end-to-end behavior.
- Do not modify production code merely to make a weak test pass. Confirm that tests assert observable behavior rather than mirroring implementation details or mocks.
- If a check fails, diagnose and fix failures caused by the change. Clearly distinguish unrelated pre-existing failures instead of hiding them.
- If verification is impossible because a tool, environment, bridge, device, or dependency is unavailable, state exactly what was and was not verified. Never imply success for a check that was not run.

### Review and Reporting

- Review the final diff for scope, duplicated logic, unnecessary state, leaky abstractions, stringly typed values, avoidable work, missed cleanup, and operations that should be concurrent.
- Re-read the user's request before finishing and confirm that every requested deliverable is present and no unrelated behavior changed.
- Report results faithfully. State passing checks plainly, include concise failure details when checks fail, and never manufacture a green result by weakening or skipping validation.
- Keep the final report concise: summarize what changed, name the important files, list the checks actually run, and call out any remaining limitation or risk.
