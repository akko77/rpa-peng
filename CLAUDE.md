# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoWorkflow is a Windows desktop GUI application for building and executing browser/desktop automation workflows visually. Built with PySide6 (Qt), it replaces hard-coded pyautogui scripts with a JSON-based workflow format (`.awf.json`). The project is in Chinese (UI and docs).

## Running

```bash
python -m app.main
```

Requires Windows 10/11, Python 3.10+, and 100% DPI scaling. Install dependencies:

```bash
pip install -r requirements.txt
```

There are no tests, lint commands, or build steps — this is a pure Python desktop app.

## Architecture

### Four-layer structure

- **`app/core/`** — Data models and execution engine (no UI dependency)
  - `workflow.py` — All dataclasses: `Workflow`, `Step`, `DataSource`, `TemplateGroup`, `Filter`, `WorkflowSettings`. `NESTED_BODY_FIELDS` maps control-flow step types to their nested body param keys (`loop_data→body`, `if→then/else`).
  - `executor.py` — `WorkflowExecutor` runs steps on a background `QThread`. Emits Qt signals (`step_started`, `step_finished`, `log_emitted`, `finished`, `paused_changed`). Supports pause/resume/stop via threading events. Control flow (`if`, `loop_data`, `break`, `continue`) is handled inline via exception-based flow control (`_BreakSignal`, `_ContinueSignal`, `_StopSignal`).
  - `interpolator.py` — `${var}` / `${item.field}` variable substitution in step params.
  - `data_source.py` — Loads items from CSV/XLSX/JSON/inline, applies filter functions.
  - `filter_evaluator.py` — Builds filter functions from visual rules or `simpleeval` expressions.
  - `context.py` — `ExecutionContext` holds runtime variables and current loop item/index.
  - `matcher.py` — OpenCV multi-scale template matching.

- **`app/actions/`** — Step type implementations. Each action is a subclass of `ActionBase` (in `base.py`) with `type_name`, `display_name`, `execute(params, context)`. Registered in `__init__.py` via a flat import list. `is_control_flow()` distinguishes structural steps from atomic ones.

- **`app/persistence/`** — File I/O
  - `workflow_io.py` — Load/save `.awf.json` files (plain JSON, no schema validation yet).
  - `template_io.py` — Manages `templates/<group_name>/` directories with PNG variants and `meta.json`.

- **`app/ui/`** — PySide6 GUI
  - `main_window.py` — Three-column layout: step list (left), step editor (center), side tabs (right) + log panel (bottom). Runs executor on `_ExecutorThread(QThread)`.
  - `step_list_panel.py` — Tree widget for steps (supports nested bodies).
  - `step_editor_panel.py` — Dynamic form that changes based on selected step type.
  - `side_tabs/template_library.py` — Template group management with region picker.
  - `side_tabs/data_source_panel.py` — Data source config + filter builder.
  - `overlays/position_picker.py` — F8 coordinate picker overlay.
  - `overlays/region_picker.py` — Screen region selection overlay.

### Adding a new step type

1. Create `app/actions/<name>.py` with a class inheriting `ActionBase`, setting `type_name` and implementing `execute()`.
2. Import and register it in `app/actions/__init__.py` (add to the `_register()` loop).
3. Add UI editing support in `app/ui/step_editor_panel.py`.

### Data flow for execution

`MainWindow` → creates `WorkflowExecutor(workflow)` → wraps in `_ExecutorThread` → `executor.run()` iterates steps → each step gets `interpolate_dict(params, context)` → `action.execute(interpolated, context)` → signals emitted back to UI.

### Workflow JSON format

Saved as `.awf.json`. Top-level keys: `name`, `description`, `version`, `variables`, `settings`, `steps`, `templates`, `data_source`. Steps can have `on_success`/`on_failure` pointing to other step IDs within the same block. Nested bodies (for `if`/`loop_data`) are arrays of step dicts inside `params`.

### Template storage

```
templates/
  <group_name>/
    v1.png, v2.png, ...    # variant images
    meta.json               # group metadata (redundant with workflow JSON)
```

The workflow JSON is the source of truth; `meta.json` is a backup/import helper.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| F5 | Run workflow |
| Shift+F5 | Stop |
| F6 | Pause/Resume |
| F9 | Toggle breakpoint |
| F10 | Single step |
| F8 | Pick coordinate (in overlay) |
| Esc | Cancel overlay |
| Ctrl+N/O/S | New/Open/Save |
