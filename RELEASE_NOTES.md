# Release Notes — llama.cpp Control Deck v1.0.3

**Release date:** 2026-05-30

## Highlights

v1.0.3 is a UX-focused release. It significantly improves the browser control
panel with accessibility, onboarding, dark mode, batch operations, drag-and-drop
service ordering, inline validation, offline feedback, and broader RU/EN i18n.

This release does **not** include developer-only roadmap or CI audit files in the
published repository state.

## Major UX Improvements

- **Dark mode** with persisted preference and system `prefers-color-scheme`
  fallback.
- **First-run wizard** when runtime or model configuration is missing.
- **Empty Services state** with a clear **Add service** call to action.
- **Keyboard-accessible modals**: `Escape` closes dialogs, focus is trapped
  inside active modals, and the first useful field receives focus on open.
- **ARIA live announcements** for toast/status messages.
- **Offline indicator** when `/api/state` polling fails.
- **Responsive modals** with `max-height: 90vh` and internal scrolling.

## Service Management

- Batch **Start selected** / **Stop selected** actions.
- Checkbox selection for services.
- Drag-and-drop service reordering saved through `POST /api/instances/reorder`.
- **Undo delete** via button or `Ctrl+Z` / `Cmd+Z`.
- Health sparklines showing the last 10 health states per service.
- Inline service validation with debounce and live command preview updates.

## Performance & Reliability

- Adaptive refresh polling (`setTimeout`) replaces fixed `setInterval`.
- Tkinter logs refresh only when the Logs tab is active.
- Tkinter instance table updates rows in place instead of recreating the entire
  Treeview.
- `load_config()` uses an mtime-based cache with defensive `deepcopy()`.
- Local browser error telemetry is stored in `logs/web-client-errors.jsonl` via
  `POST /api/client-error`.

## Internationalization & Accessibility

- Broader RU/EN coverage for old hardcoded labels and new UX controls.
- Path picker file sizes now display as human-readable IEC units.
- Text inputs use `dir="auto"` for mixed LTR/RTL text.

## Upgrade Notes

No breaking changes. Existing `config.json` files remain compatible.

If you use the Web UI, refresh the page after upgrading to load the new CSS and
JavaScript assets.

## Files Changed

- `config.py`
- `control_web.py`
- `llama_cpp_gui.py`
- `static/control.css`
- `static/control.js`
- `templates/index.html`
- `CHANGELOG.md`
- `README.md`
- `pyproject.toml`

## Compatibility

| Component | Minimum | Tested |
|-----------|---------|--------|
| Python | 3.10 | 3.12 |
| OS | Linux | Ubuntu 22.04/24.04 |
| Browser | any modern | Chromium 136, Firefox 139 |

---

Full changelog: [CHANGELOG.md](CHANGELOG.md)
