# UX Roadmap — llama.cpp Control Deck

> **Version:** 1.0  
> **Last updated:** 2026-05-30  
> **Status:** Approved for implementation  
> **Source:** Post-v1.0.2 audit and release review

---

## 1. Performance & Responsiveness (P0 — Critical)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| PERF-01 | **Debounced polling** | `setInterval(refresh, 2500)` spams requests on slow networks | Adaptive `setTimeout`: if request >1.5s → interval 5s; if <500ms → keep 2.5s | Network tab shows ≤1 active `/api/state` at any time | TBD | v1.1.0 |
| PERF-02 | **Incremental rendering** | `render()` overwrites ALL fields even when unchanged | Server returns `etag` or `last_modified`; client skips render if identical | `render()` CPU time drops 70%+ in profiler | TBD | v1.1.0 |
| PERF-03 | **Lazy log loading** | Logs read from disk every 3s via `refresh_logs` inside `refresh_status` | Split polling: status every 3s, logs only when Logs tab / modal is active | `strace` shows no `.log` reads when Server tab active | TBD | v1.1.0 |
| PERF-04 | **Virtual Treeview updates** | Tkinter Treeview fully recreated (`delete(*children)`) causing flicker | Update existing items via `tree.item(iid, values=...)` instead of delete+insert | No visual flicker with 20+ instances | TBD | v1.1.0 |
| PERF-05 | **Config cache** | `load_config()` runs `json.load` + `deepcopy` + `merge_defaults` on EVERY call | `lru_cache` with TTL 2s or in-memory cache with `mtime` check | `load_config` <1% CPU at 10 rps | TBD | v1.2.0 |

---

## 2. Accessibility (P0/P1 — High Priority)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| A11Y-01 | **ARIA live regions** | Toasts and status changes not announced to screen readers | Add `<div aria-live="polite" aria-atomic="true" class="sr-only">` for critical messages | NVDA/VoiceOver announces "Server started", "Validation error" | TBD | v1.1.0 |
| A11Y-02 | **Keyboard modal navigation** | Modals don't close on `Escape`; no `Tab` trap | `keydown` listener: `Escape` → close; `Tab` cycles focus inside modal | Full modal control via keyboard only | TBD | v1.1.0 |
| A11Y-03 | **Focus management** | Focus stays on trigger button after modal opens | `focus()` on first modal field (`svc-name`) on open | `document.activeElement` inside modal immediately | TBD | v1.1.0 |
| A11Y-04 | **Label association** | Many inputs lack `for`/`id` linkage; buttons lack `aria-label` | Add `id` to every input, `for` to every label, `aria-label` to icon buttons | WAVE / Lighthouse audit: 0 label/form errors | TBD | v1.1.0 |
| A11Y-05 | **Color-blind safety** | Status "ready/stopped" relies ONLY on green/red chips | Add text prefix + SVG icons with `aria-label`: `● ready` / `● stopped` | Protanopia user distinguishes statuses | TBD | v1.2.0 |

---

## 3. UI & Visual Design (P1 — Important)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| UI-01 | **Dark mode** | Only `color-scheme: light`; night usage strains eyes | `prefers-color-scheme: dark` + manual toggle in header + `localStorage` | Auto-switch on system dark mode; manual toggle persists | TBD | v1.2.0 |
| UI-02 | **Skeleton screens** | "Loading..." in `friendly-status` looks like an error | Skeleton placeholders for service cards and input fields | FCP shows placeholders, not broken layout | TBD | v1.2.0 |
| UI-03 | **Inline validation** | Errors appear only after "Save" or "Validate" click | Debounced `fetch('/api/instances/validate')` on `input`/`change` (400ms) | "Port busy" shows immediately on typing, not after Save | TBD | v1.2.0 |
| UI-04 | **Progressive disclosure** | Advanced tab has 20+ fields — cognitive overload | Group into collapsible sub-sections: GPU, Memory, Compatibility, Experimental | New user sees 4 groups vs 16 scattered fields | TBD | v1.2.0 |
| UI-05 | **Drag & drop instances** | No way to reorder instances | HTML5 DnD or SortableJS for service cards | Order in UI matches `config.json["instances"]` after drop | TBD | v1.3.0 |
| UI-06 | **Responsive modals** | Service modal overflows on 1366×768 screens | `max-height: 90vh` + `overflow-y: auto` for `.modal-panel` | Modal fully visible without page scroll | TBD | v1.1.0 |

---

## 4. Onboarding & Error Recovery (P0 — Critical for Retention)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| ONB-01 | **First-run wizard** | Empty fields for Python, llama-server, model — unclear start | Auto-show wizard if `llama_server_binary` empty: Step 1 Detect, Step 2 Model, Step 3 Start | % users with running server within 5 min of first open | TBD | v1.1.0 |
| ONB-02 | **Empty state CTA** | Empty Services block shows nothing | Illustration + "No services yet. [Add your first service]" primary button | Keyboard-only user sees CTA in empty state | TBD | v1.1.0 |
| ONB-03 | **Error recovery hints** | "llama-server exited immediately" — no actionable guidance | Parse tail log for known patterns: `CUDA error` → reduce GPU layers, `port in use` → change port | Top 5 errors have inline actionable hints | TBD | v1.1.0 |
| ONB-04 | **Undo / Redo** | No way to recover deleted instance | `Ctrl+Z` in web UI; store last 5 actions in `state.history` | Deleted instance restored via Ctrl+Z without reload | TBD | v1.3.0 |

---

## 5. Localization & Internationalization (P1 — Important)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| I18N-01 | **Full i18n coverage** | Not all labels have `data-i18n`; Tkinter GUI is Russian-only | Add missing keys to `I18N[ru]` and `I18N[en]`; Tkinter reads `config["ui_language"]` | 0 untranslated strings per Lighthouse; Tkinter tooltips switch language | TBD | v1.2.0 |
| I18N-02 | **RTL support** | CSS assumes LTR only | Logical CSS properties (`margin-inline-start`) + `dir="auto"` on text fields | Arabic/Hebrew text renders correctly | TBD | v1.3.0 |
| I18N-03 | **Smart formatting** | Uptime shows "1234s"; file sizes raw bytes | `Intl.RelativeTimeFormat` + `Intl.NumberFormat` | "20 minutes ago", "1.2 GiB" instead of raw numbers | TBD | v1.2.0 |

---

## 6. Reliability & Feedback (P1 — Important)

| ID | Feature | Problem | Solution | Success Criteria | Owner | Target |
|----|---------|---------|----------|----------------|-------|--------|
| REL-01 | **Offline indicator** | If `control_web.py` crashes, page just stops updating | `navigator.onLine` + `fetch` catch → red banner "Connection lost. Retrying..." with exponential backoff | User sees clear status instead of frozen UI | TBD | v1.2.0 |
| REL-02 | **Destructive action confirmation** | "Delete" executes immediately | Inline confirmation: "Are you sure? [Cancel] [Delete]" or 3s undo toast | 0 accidental deletions; undo within 3s | TBD | v1.2.0 |
| REL-03 | **Batch operations** | Cannot select multiple instances | Checkboxes in card headers + toolbar "Start selected (3)" / "Stop selected (3)" | Start 5 servers in 2 clicks vs 10 | TBD | v1.3.0 |
| REL-04 | **Health sparklines** | Health status is binary; no trend visibility | Mini SVG sparkline in service card: last 10 health checks | Visual "flapping" health checks visible | TBD | v1.3.0 |

---

## 7. UX Testing & Tooling (P2 — Foundational)

| ID | Practice | Tool | What to Measure | Frequency | Owner |
|----|----------|------|-----------------|-----------|-------|
| TEST-01 | **Lighthouse CI** | `lighthouse-ci` in GitHub Actions | Performance ≥90, Accessibility ≥95, Best Practices ≥95 | Every PR | TBD |
| TEST-02 | **Usability testing** | 5-task script for new users | Task 1: Start first server ≤3 min; Task 2: Add embeddings ≤2 min; Task 3: Diagnose crash from logs ≤1 min | Monthly | TBD |
| TEST-03 | **Interaction analytics** | Self-hosted `umami` or `plausible` | Click heatmaps; ignored buttons; modal close rates | Continuous | TBD |
| TEST-04 | **Error telemetry** | Sentry self-hosted or `POST /api/error` | Count of JS `unhandledrejection` and `console.error` | Continuous | TBD |

---

## Implementation Roadmap

### v1.1.0 (Q3 2026)
**Theme:** Performance & Accessibility Foundation

- [ ] PERF-01 Debounced polling
- [ ] PERF-03 Lazy log loading
- [ ] PERF-04 Virtual Treeview updates
- [ ] A11Y-01 ARIA live regions
- [ ] A11Y-02 Keyboard modal navigation
- [ ] A11Y-03 Focus management
- [ ] UI-06 Responsive modals
- [ ] ONB-01 First-run wizard
- [ ] ONB-02 Empty state CTA
- [ ] ONB-03 Error recovery hints

### v1.2.0 (Q4 2026)
**Theme:** Polish & Offline Reliability

- [ ] PERF-05 Config cache
- [ ] A11Y-05 Color-blind safety
- [ ] UI-01 Dark mode
- [ ] UI-02 Skeleton screens
- [ ] UI-03 Inline validation
- [ ] UI-04 Progressive disclosure
- [ ] I18N-01 Full i18n coverage
- [ ] I18N-03 Smart formatting
- [ ] REL-01 Offline indicator
- [ ] REL-02 Destructive action confirmation
- [ ] REL-03 Batch operations

### v1.3.0 (Q1 2027)
**Theme:** Power User Features & Advanced UX

- [ ] PERF-02 Incremental rendering
- [ ] UI-05 Drag & drop instances
- [ ] I18N-02 RTL support
- [ ] ONB-04 Undo / Redo
- [ ] REL-04 Health sparklines
- [ ] TEST-01 Lighthouse CI integration

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-30 | P0 assigned to Performance + Onboarding | These directly impact first-time user retention |
| 2026-05-30 | Accessibility grouped as P0/P1 | WCAG compliance is non-negotiable for public tool; partial fixes in v1.1.0 |
| 2026-05-30 | Dark mode deferred to v1.2.0 | Requires full colour token audit; not blocking core functionality |
| 2026-05-30 | Batch operations deferred to v1.3.0 | Needs selection state architecture; lower immediate impact |

---

## How to Update This Document

1. After each release, mark completed items with `[x]` and move them to "Completed" section.
2. When new UX issues are discovered, add them with next available ID and assign priority.
3. Re-prioritize quarterly based on user feedback and telemetry data from TEST-03 and TEST-04.
4. Archive decisions to Decision Log with date and rationale.

---

*This roadmap is a living document. Last synchronized with codebase at commit `850fbcc` (v1.0.2).*
