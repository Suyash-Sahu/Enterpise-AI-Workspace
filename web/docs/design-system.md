# Enterprise AI Workspace — Design System

Sleek foundation: modern, minimal, calm. Less chrome, more content. This
document is the single source of truth for tokens and shared-component rules.
It is enforced in code review with the checklist at the end.

---

## 1. Context and goals

- **One token system.** Every color, radius, shadow, and font comes from a
  semantic token defined in [`src/app/globals.css`](../src/app/globals.css).
  Screens never pick raw palette values (`bg-indigo-600`, `text-emerald-400`)
  except inside a token definition.
- **Two themes, one contract.** Light and dark are the same tokens with
  different values. Never hard-code a color that only works in one theme.
- **Accessibility is a requirement, not a pass.** WCAG 2.2 AA everywhere:
  body text ≥ 4.5:1, large text and non-text UI ≥ 3:1, a visible
  `:focus-visible` indicator on every interactive element, full keyboard
  operation, `prefers-reduced-motion` respected.
- **Brand primary is indigo `#4F46E5`** (`#6366F1` in dark). Do not change it.

---

## 2. Design tokens and foundations

### 2.1 Color — 60 / 30 / 10

| Role | Token (utility) | Light | Dark | Use for |
|---|---|---|---|---|
| **60 — page** | `bg-background` | `#fafafa` | `#0b0e14` | app/page ground |
| | `bg-surface` / `bg-card` | `#ffffff` | `#151922` | cards, panels, sidebar, header |
| | `bg-popover` | `#ffffff` | `#151922` | menus, dropdowns, tooltips |
| **30 — structure** | `text-foreground` | `#111827` | `#f3f4f6` | primary text, headings |
| | `text-muted-foreground` | `#5b6472` | `#9aa4b2` | secondary text, captions, labels |
| | `border-border` | `#e4e7ec` | `#262b36` | dividers, card edges |
| | `border-input` | `#d6dae1` | `#2f3542` | form field borders |
| | `bg-muted` | `#f2f3f7` | `#1c2230` | inset areas, hover rows, skeletons |
| | `bg-secondary` `text-secondary-foreground` | `#f2f3f7` / `#1f2430` | `#1c2230` / `#f3f4f6` | secondary buttons |
| | `bg-accent` `text-accent-foreground` | `#f2f3f7` / `#111827` | `#1c2230` / `#f3f4f6` | hover surface for ghost items |
| **10 — accent** | `bg-primary` `text-primary-foreground` | `#4f46e5` / `#fff` | `#6366f1` / `#fff` | primary action, active nav, key emphasis |
| | `ring-ring` | `#4f46e5` | `#6366f1` | focus ring |
| **status** | `*-destructive` | `#dc2626` / `#fff` | `#f87171` / `#0b0e14` | errors, destructive actions |
| | `*-success` | `#047857` / `#fff` | `#34d399` / `#0b0e14` | healthy, connected, done |
| | `*-warning` | `#b45309` / `#fff` | `#fbbf24` / `#0b0e14` | degraded, "soon", caution |
| | `*-info` | `#0369a1` / `#fff` | `#38bdf8` / `#0b0e14` | neutral notices, "live" |

Legacy aliases `--local` (→ success) and `--cloud` (→ info) are kept only for
existing call sites; do not introduce new uses.

**Status tint pattern:** `bg-<status>/10 text-<status>` for a soft chip;
`bg-<status> text-<status>-foreground` for a solid badge. Both pass AA with the
values above.

### 2.2 Typography

- **Family:** `font-sans` = Inter (variable `--font-inter`). `font-mono` =
  JetBrains Mono — only for genuine machine output: code, IDs, JSON, key
  bindings, request paths. Not for labels, badges, timestamps, or headings.
- **Weights:** `400` body · `500` medium emphasis / labels · `600` headings &
  buttons · `700` reserved for the single largest heading on a page.
  Do **not** use `font-extrabold`.
- **Scale** (Tailwind `text-*`, all with sensible default line-heights):

  | Token | Size | Weight | Use |
  |---|---|---|---|
  | `text-3xl` … `text-5xl`/`text-6xl` | 30–60px | 600–700 | marketing hero only |
  | `text-2xl` | 24px | 600 | page title (`PageHeader`) |
  | `text-lg` | 18px | 600 | section / card group title |
  | `text-sm` (`text-base` for long-form) | 14–16px | 400 | body |
  | `text-xs` | 12px | 500 | labels, captions, table meta |
  | `text-[11px]` / `text-[10px]` | — | — | avoid; only dense data tables |

### 2.3 Spacing — 8-point rhythm

Use only these steps (Tailwind units in parentheses):

`4 (1) · 8 (2) · 12 (3) · 16 (4) · 24 (6) · 32 (8) · 48 (12) · 64 (16) · 96 (24)`

- Card padding: `p-4` (compact) or `p-6` (default).
- Grid/stack gaps: `gap-2` / `gap-3` / `gap-4` / `gap-6`.
- Page section rhythm (marketing): `py-16` or `py-24`.
- **Banned:** `p-3.5`, `p-2.5`, `gap-2.5`, `space-y-0.5`, `mt-0.5`, and other
  half-steps. Round to the nearest allowed step.

### 2.4 Radius

| Token | Value | Use |
|---|---|---|
| `rounded-sm` / `rounded-md` (…`lg`) | 8px | buttons, inputs, chips, small controls |
| `rounded-md` (…`xl` / `2xl`) | 12px | cards, panels, popovers, modals, sheets |
| `rounded-full` | pill | badges, avatars, toggles, icon buttons |

`rounded-lg`→8px, `rounded-xl`/`rounded-2xl`→12px are folded to these two steps
in the theme. **Do not use `rounded-3xl` / `rounded-4xl`.**

### 2.5 Elevation

Two levels only:

- `shadow-sm` — resting card / raised surface.
- `shadow-md` — popover, dropdown, modal, sheet, toast.

`shadow-lg` / `shadow-xl` / `shadow-2xl` are folded to `shadow-md`.
**Do not use colored shadows** (`shadow-primary/25` etc.) — use `ring-1` or a
border for emphasis instead.

### 2.6 Motion

- Durations: `150ms` (hover/tap feedback) · `200ms` (default; enter) ·
  `300ms` (drawer / modal / layout). Nothing longer.
- Easing: `--ease-standard` = `cubic-bezier(0.4, 0, 0.2, 1)` (Tailwind default
  transition timing is set to this).
- **No infinite animations.** No looping pulses, bouncing indicators, or
  perpetual gradient drifts. One-shot enter/exit only.
- Every non-trivial animation must be neutralised under
  `@media (prefers-reduced-motion: reduce)` — the global base rule already
  clamps `animation`/`transition` durations; Framer Motion components must also
  check `useReducedMotion()` before running.

---

## 3. Component-level rules

Shared primitives live in `src/components/ui` (design primitives) and
`src/components/shared` (composed patterns). Screens compose these — they do
**not** re-implement them with raw `<div>` / `<button>`.

### Required states

Every interactive component defines, with tokens:

`default · hover · active · focus-visible · disabled · loading · error`
(as applicable to the component).

- `focus-visible`: `ring-2 ring-ring` + `ring-offset-2 ring-offset-background`
  (or the base outline). Never `outline-none` without a replacement.
- `disabled`: `opacity-50 pointer-events-none`, `aria-disabled` where the
  element stays in the tree.
- `loading`: show a spinner/skeleton, keep layout height stable, set
  `aria-busy`.

### Data screens

Use one wrapper so every data view has the same four states:

```
loading  → skeleton (stable height, aria-busy)
empty    → <EmptyState> (icon, title, one-line reason, optional action)
error    → <ConnectorErrorState> / inline alert (reason + retry / connect)
content  → the real UI
```

### Buttons

Variants: `default` (primary), `secondary`, `outline`, `ghost`,
`destructive`, `link`. Sizes: `sm` `default` `lg` `icon`. One primary action
per view; everything else `secondary` / `ghost` / `link`.

### Page header

`PageHeader` is the only page-title component: theme-aware `text-foreground`
title (`text-2xl font-semibold`), `text-muted-foreground` description,
optional breadcrumbs and a right-aligned action slot.

---

## 4. Accessibility — testable acceptance criteria

- [ ] Contrast: body text ≥ 4.5:1, large/UI ≥ 3:1, in **both** themes.
- [ ] Every interactive element reaches a visible focus state via keyboard.
- [ ] Tab order matches visual order; no keyboard trap; `Esc` closes
      overlays; focus returns to the trigger on close.
- [ ] Modals/drawers use a labelled dialog, `aria-modal`, focus trap.
- [ ] Command palette: `⌘/Ctrl-K` opens, arrows move, `Enter` selects,
      `Esc` closes.
- [ ] Icons that carry meaning have `aria-label` / `sr-only` text; decorative
      icons are `aria-hidden`.
- [ ] Live regions (`role="status"` / `aria-live`) for async results and toasts.
- [ ] `prefers-reduced-motion`: no motion beyond a near-instant fade.

---

## 5. Content and tone

Concise, confident, helpful. Sentence case for everything except proper nouns.

| Do | Don't |
|---|---|
| "Connect your Google account" | "You are not connected!!" |
| "No documents yet" | "Empty" |
| "Couldn't reach the workspace API" | "Error 502" |
| "Request approval to send" | "Submit" |

Buttons are verbs (`Save changes`, `Connect account`). Empty states name the
thing and the next step. Errors say what failed and what to do.

---

## 6. Anti-patterns (prohibited)

- Raw palette colors in screens (`bg-indigo-600`, `text-emerald-400`,
  `border-slate-800`, `bg-zinc-900`) — use tokens.
- `text-white` / `text-black` for text that sits on a themed surface.
- Undefined utilities from a missing token (pre-Phase-0 state).
- `font-extrabold`; `font-mono` on non-machine text.
- Half-step spacing (`p-3.5`, `gap-2.5`).
- `rounded-3xl` / `rounded-4xl`; colored or `shadow-2xl` elevation.
- Infinite animations; motion without a reduced-motion path.
- Re-implementing `Button` / `Card` / `Badge` / `PageHeader` with raw elements.
- Two components for one job (parallel shells, duplicate providers,
  `PageHeader` + `PageHeading`).

---

## 7. Migration guidance

1. **Colors:** replace `bg-<palette>-<n>` → nearest token. Icon tiles:
   `bg-primary/10 text-primary` or a status token, not a per-screen hue.
2. **Text:** `text-white`/`text-slate-200` on content → `text-foreground` /
   `text-muted-foreground`. Delete `drop-shadow` on text.
3. **Radius:** `rounded-3xl`/`rounded-4xl` → `rounded-md`; pills →
   `rounded-full`.
4. **Shadow:** `shadow-lg|xl|2xl` → `shadow-md`; `shadow-primary/*` → remove.
5. **Spacing:** snap half-steps to the 8-pt scale.
6. **Weights:** `font-extrabold` → `font-semibold` (or `font-bold` for the
   single hero heading).
7. **Cards/buttons:** hand-rolled `<div class="rounded-2xl border bg-surface">`
   → `<Card>`; `<button class="… bg-primary …">` → `<Button>`.
8. **States:** ensure every data view renders loading, empty, error, content.

---

## 8. QA checklist (run in code review)

- [ ] No raw palette color classes in `src/app` / screen components.
- [ ] `npx tsc --noEmit` clean; `next build` clean; tests green.
- [ ] No new ESLint errors/warnings vs. the branch baseline.
- [ ] Light and dark both legible on every changed screen; theme persists.
- [ ] Keyboard: every control focusable with a visible ring; overlays trap
      and restore focus; `Esc` works.
- [ ] 375 / 768 / 1280 / 1920 — no horizontal scroll; sidebar is a drawer
      below `lg`, docked at/above `lg`; content max-width ≈ 1400px.
- [ ] Loading / empty / error / content all present for data views.
- [ ] Only tokens for color, ≤ 2 radii, ≤ 2 shadow levels, 8-pt spacing.
- [ ] No infinite animation; transitions ≤ 300ms; reduced-motion honoured.
- [ ] No dead imports, no duplicate components, no debug code, no temp files.
