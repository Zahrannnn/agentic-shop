---
name: agentic-shop Design System
description: Confident-curator shopping UI — restrained paper surface, coral accent, editorial precision.
colors:
  cream: "oklch(98% 0.014 88)"
  card: "oklch(99.5% 0.01 88)"
  ink: "oklch(22% 0.03 265)"
  pencil: "oklch(48% 0.035 265)"
  hairline: "oklch(95% 0.018 88)"
  coral: "oklch(58% 0.2 25)"
  lavender-wash: "oklch(93% 0.045 285)"
  teal-quiet: "oklch(52% 0.14 195)"
typography:
typography:
  display:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Space Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.05em"
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.625rem"
spacing:
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.coral}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
---

# Design System: agentic-shop

## 1. Overview

**Creative North Star: "The Curator's Desk"**

A personal shopper's desk the evening before a flight: warm paper surface, decisive
ink, and exactly one recommendation underlined. The system is built on **restraint as
confidence** — tinted neutrals carry the surface, a single coral accent marks where
the agent commits, and typography does the persuasion. Whitespace is generous; density
is earned by content, not imposed by chrome.

This system explicitly rejects the anti-references in PRODUCT.md: no AI-SaaS gradients,
no glassy blur cards, no Inter-everywhere defaults, no floating pill buttons, no
identical card rows. It also rejects dark-mode-by-default (the scene is an evening
desk under lamplight, which paper-white serves better than a dashboard black), and it
rejects decoration that doesn't carry information.

**Key Characteristics:**
- Paper-first light surface; ink-weight contrast instead of color contrast
- One coral accent, spent only where the agent commits
- Editorial scale jumps (≥1.25 ratio) over many same-weight steps
- Hairline borders and tonal steps for depth; shadows reserved for true overlays
- Ease-out micro-transitions only; nothing bounces, nothing glows

## 2. Colors

Strategy: **Restrained** — tinted neutrals plus one accent under 10% of any screen.
Neutrals are tinted toward the warm cream family so the whole surface
belongs to one family.

### Primary
- **Coral** (oklch(58% 0.2 25)): the agent's voice made visible — the REAL/MOCK commitment badge, primary actions, focus rings. If it appears twice on one screen without a second commitment, that's already too much.

### Neutral
- **Cream** (oklch(98% 0.014 88)): page background; warm, never pure white.
- **Card** (oklch(99.5% 0.01 88)): raised surfaces one step above Cream.
- **Ink** (oklch(22% 0.03 265)): primary text. Never pure black.
- **Pencil** (oklch(48% 0.035 265)): secondary text, metadata, timestamps.
- **Hairline / Muted** (oklch(95% 0.018 88)): all borders, dividers, recessed fills.

### Named Rules
**The One Underline Rule.** The coral accent marks the agent's commitment — the
recommended pick, the single primary action. Rarity is the point; on any screen it
covers under 10% of pixels.

**The No-Pure-Pixel Rule.** Pure `#000` and `#fff` are forbidden. Every neutral is
tinted toward the ink hue.

## 3. Typography

**Direction:** Editorial precision — a single warm-technical grotesque sans across the
whole UI `[font pairing to be chosen at implementation]`; a tabular/mono cut is
allowed for numerals, prices, and attribute values so comparison columns align like
an instrument.

**Character:** Confidence through restraint — weight and scale jumps do the work;
letter-spacing is reserved for small uppercase labels.

### Hierarchy
- **Display** (600, ~1.6–2rem, 1.1): page-level statements only; one per view.
- **Headline** (600, ~1.25rem, 1.25): section and turn headings.
- **Title** (500, ~1rem, 1.4): product names, card titles.
- **Body** (400, ~0.9375rem, 1.6, max 65–75ch): the agent's prose and reasons.
- **Label** (500, ~0.75rem, +0.05em tracking, uppercase): attribute names, stepper stages, metadata.

### Named Rules
**The Scale Rule.** Adjacent type steps differ by ≥1.25×. If two sizes feel close,
they're the same size — pick one.

**The Numerals Rule.** Prices and attribute values render in the tabular cut so
comparison columns align; never proportionals in a table.

## 4. Elevation

Flat by default. Depth comes from tonal steps (Paper vs Desk) and hairline borders,
never from resting shadows. A single low-alpha shadow vocabulary exists for true
overlays only (dialog, popover): `0 8px 32px rgba(ink, 0.08–0.12)`. Focus is always a
2px coral ring at 2px offset, never a glow.

### Named Rules
**The Paper Rule.** Surfaces are flat at rest. Shadows appear only when an element
genuinely floats above the page (overlay layer), never for hover decoration.

## 5. Components

The renderer registry ships six plan-driven components (shadcn primitives on the
tokens above): product cards (name, tabular price, ANC badge, provenance id,
Details/Add-to-cart), preference chips, the comparison table (uppercase Label row
headers, tabular mono values), product detail cards, cart tables with a TOTAL footer
row, and quiet text panels. Plan actions render as outline buttons; the single
primary (Teal Ink) control per view is the agent's commitment or the composer's Send.

The transcript chrome: a sticky full-width header (wordmark, Browse-catalog, mode
badge), a sticky full-width composer bar, thinking skeletons (three Skeleton lines
under a "Thinking… Ns" timer with reassurance rotation), and plan skeletons while a
plan document is incoming.

## 6. Do's and Don'ts

### Do:
- **Do** spend Teal Ink on exactly one commitment per view (the recommended pick or the primary action).
- **Do** use hairline borders (`1px` Hairline) and tonal steps for structure; borders are structure, not decoration.
- **Do** keep agent prose at 65–75ch with 1.6 line-height; reasons read like edited copy.
- **Do** align prices and attribute values in a tabular/mono cut inside comparison tables.
- **Do** respect `prefers-reduced-motion`: transitions collapse to opacity only.

### Don't:
- **Don't** use purple-to-blue gradients, glassy blur cards, Inter-everywhere defaults, floating pill buttons, or identical three-card feature rows — the AI-SaaS gradient anti-reference is banned by name.
- **Don't** use side-stripe borders (`border-left/right` > 1px as colored accents) on cards, list items, or callouts.
- **Don't** use gradient text (`background-clip: text`), bounce/elastic easing, or layout-animating transitions.
- **Don't** build the hero-metric template (big number + small label + gradient accent) anywhere in the UI.
- **Don't** render identical same-sized card grids with icon + heading + text; the comparison table and ranked grid earn their differences.
- **Don't** reach for a modal first; inline and progressive disclosure come first (dialogs are for true interruptions only).
- **Don't** use pure `#000`/`#fff`, and don't introduce a second accent hue; the palette is coral plus tinted neutrals, full stop.
