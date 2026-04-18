# Accessibility — FlowPulse

A stadium holds 40,000 people. Some of them use wheelchairs. Some use screen readers. Some don't speak the local language. Some are on flaky data. Some can see the map, but not the colours. FlowPulse is designed so every one of them can **know where the short queues are** and **get there without help**.

Accessibility isn't a compliance checkbox on this project — it's a first-class feature with its own toggle in the nav.

## Features

### 1. Accessible Mode (top-nav toggle)

A single switch that makes the whole PWA more usable for diverse conditions. Persists in `localStorage`; auto-enables when the OS exposes `prefers-contrast: more` or `prefers-reduced-motion: reduce`.

When **on**:

| Change | Benefit |
|---|---|
| Darker borders, 2 px minimum | Low-vision, high-contrast need |
| Tap targets bumped to ≥ 48 × 48 px | Motor disability |
| All SVG animations paused | Vestibular disorders, motion sensitivity, low-end devices |
| Score pills carry a **shape** (● good, ▲ watch, ■ action) on top of colour | Colour-blindness (deuteranopia, tritanopia), low-colour screens |
| Text-only map view available (sortable table of zones) | Screen readers, CLI-like workflows, low-bandwidth |
| Critical alerts play a short beep + vibrate (if device supports) | Deaf / hard-of-hearing on mobile |

### 2. Hindi locale

`/hi` serves a Hindi Welcome page (`frontend/app/(hi)/page.tsx`). A language toggle lives in the footer. The English/Hindi split demonstrates the i18n seam; more locales are one folder away.

### 3. Keyboard navigation

Every interactive element is reachable via Tab / Shift-Tab. A visible focus ring (`:focus-visible` only — no mouse-click noise) makes the cursor discoverable.

| Shortcut | Effect |
|---|---|
| `Tab` / `Shift-Tab` | Move between controls |
| `Enter` / `Space` | Activate a focused zone, button, link |
| `/` | Focus the chat input (on `/chat`) |
| `Esc` | Dismiss a toast or return focus to the map |
| Arrow keys (map focused) | Scroll focus between neighbouring zones |

### 4. Screen-reader support

Tested with NVDA (Windows) and VoiceOver (macOS).

- `<main id="main">` landmark + a "Skip to main content" link as the first focusable element
- SVG map has `role="img"` + `aria-label` + a hidden `<desc>` describing the colour semantics and flow-particle meaning
- Chat log is an `aria-live="polite"` region so new messages are announced without interrupting
- Critical alert banners use `aria-live="assertive"`
- Tool-call chips include `title=` showing the argument JSON
- Every form input has an explicit `<label htmlFor=…>`

### 5. Reduced-motion respect

Default CSS honours `prefers-reduced-motion: reduce` — all `@keyframes` disabled. The StadiumMap's JavaScript also checks `matchMedia("(prefers-reduced-motion: reduce)").matches` and skips the SVG `<animate>` elements + flow particles entirely. Users who need it see a static, information-equivalent map.

### 6. Colour palette — colour-blind safe by design

All three Flow-Score bands were chosen to remain distinguishable under Daltonize-emulated deuteranopia, protanopia, and tritanopia. When Accessible Mode is on, the shape token (circle/triangle/square) provides a second channel so the palette is not the sole signal.

- Good (80-100): `#16a34a` with circle shape
- Watch (50-79): `#d97706` with triangle shape
- Action (0-49): `#dc2626` with square shape

All combinations meet WCAG AA contrast (4.5:1) against the background; most meet AAA (7:1). See `docs/screenshots/contrast-check.png` for a WebAIM Contrast Checker result.

## Verification

| Check | How | Target |
|---|---|---|
| Lighthouse a11y score | `.lighthouserc.json`, CI job runs against live URL | ≥ 95 |
| axe-core violations | `frontend/e2e/a11y.spec.ts` under Playwright | 0 critical/serious |
| Keyboard-only walkthrough | `docs/ACCESSIBILITY-manual-tests.md` checklist | every page traversable without mouse |
| Screen-reader walkthrough | NVDA / VoiceOver ten-point script (see below) | all content + actions discoverable |
| Contrast audit | WebAIM Contrast Checker screenshot | all combinations AA or better |

### NVDA / VoiceOver walkthrough script (10 points)

1. Land on `/`. Focus should be on the "Skip to main content" link.
2. Tab once — brand link "FlowPulse home".
3. Tab to "Welcome", "Live Map", "Concierge", "Ops Console" — `aria-current="page"` announced on the active one.
4. Press Enter on "Live Map". The WebSocket status chip announces "Streaming live" via `aria-live="polite"`.
5. Tab into the map. First zone focuses; its `aria-label` reads as "Gate A, Flow Score 93 out of 100, calm, 0 of 800 people, 0 minute wait."
6. Tab through 3-4 zones. Any critical-level zone reads with "critical" in the announcement.
7. Navigate to `/chat`. `aria-live="polite"` log announces the bot greeting. Type a question in the chat input (labelled "Ask the concierge").
8. Response arrives — announced as a new entry in the log, followed by the tool-chip list.
9. Navigate to `/ops`. The login form's fields both have explicit `<label>` tags. Log in.
10. Hit "Propose Actions". Toast appears and is announced via `aria-live="polite"`. Tab to an action card, press Enter on "Apply". Toast result is announced.

## Known gaps

- Full right-to-left (RTL) support isn't tested; would need `dir="rtl"` on the html tag for Arabic/Hebrew locales.
- Voice-control software (Dragon NaturallySpeaking, Talon Voice) isn't explicitly tested. Commands like "click Apply" should work since every button has visible text.
- The Mermaid architecture diagrams in docs aren't SVG-accessible by default; alt-text summaries accompany each.

## What winning accessibility looks like

Two recent Gemini Competition winners (Vite Vere and ViddyScribe) **won** because their a11y story was the product. FlowPulse takes inspiration: we didn't invent a disability-first app, but we did make Accessible Mode a feature a judge can toggle and demo in 20 seconds.
