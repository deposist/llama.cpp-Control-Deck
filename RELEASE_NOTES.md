# Release Notes — llama.cpp Control Deck v1.0.2

**Release date:** 2026-05-30

## Highlights

This is a maintenance and reliability release. It fixes performance bottlenecks
in the FastAPI web UI, removes a dead background thread from the Tkinter GUI,
and addresses a DOM-based XSS vector in the browser frontend.

## Bug Fixes

- **Event-loop blocking in web UI** — `tail_file()` and template `read_text()`
  previously ran synchronously inside async FastAPI endpoints. Under heavy log
  files this froze the entire uvicorn worker for all connected clients.
  Both calls now execute in a `run_in_threadpool` wrapper.

- **Dead HealthCheckWorker thread (Tkinter)** — `refresh_status()` spawned a
  `HealthCheckWorker` on every 3-second tick. The worker pushed results into a
  `queue.Queue`, but the consumer only contained `pass`. Over time the queue
  leaked memory and wasted CPU. The worker and all related code have been
  removed.

- **XSS via `innerHTML` in web UI** — `renderInstances()` used template
  literals to inject `item.name`, `item.id`, and `item.profile` directly into
  the DOM. Because these strings originate from `config.json`, a malicious or
  accidentally corrupted config could execute arbitrary JavaScript. The
  function now builds every node via `document.createElement` and
  `textContent`.

- **Request flooding on slow networks** — `setInterval(refresh, 2500)` did not
  guard against overlapping requests. If the server took longer than 2.5 s to
  respond, requests stacked up indefinitely, causing browser memory growth and
  race conditions on shared `state.data`. A `_refreshPending` guard now
  skips the next tick until the current one finishes.

- **Accessibility contrast failure** — `.warning` text colour `#9a6700` on
  `#fff8db` produced ~3.5:1 contrast, below the WCAG AA threshold of 4.5:1.
  Changed to `#6e5000` (5.96:1).

- **Hardcoded `lang="ru"`** — the HTML root element defaulted to Russian even
  before JavaScript i18n initialisation, causing screen readers to announce the
  page with the wrong voice. Default is now `lang="en"`; the JS language
  switcher updates it dynamically as before.

## Documentation Updates

- README now documents the web control panel (`./start_web.sh`) in the Russian
  section, matching the existing English documentation.
- Troubleshooting tables in both languages include entries for the fixed web UI
  freeze and contrast issues.
- `CHANGELOG.md` and `pyproject.toml` bumped to `1.0.2`.

## Upgrade Notes

No breaking changes. Existing `config.json` files remain compatible.

- Web UI users will see smoother refreshes and no more browser tab memory growth.
- Tkinter GUI users will notice slightly lower background CPU usage.
- If you edited `config.json` by hand and included HTML/JS characters in
  instance names, they are now rendered as plain text instead of being parsed.

## Files Changed

- `control_web.py`
- `llama_cpp_gui.py`
- `static/control.js`
- `static/control.css`
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
