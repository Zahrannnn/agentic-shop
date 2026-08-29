# Product

## Register

product

## Users

A consumer shopping with a specific need in mind ("headphones for long flights under
$200, noise cancellation matters") on a laptop, often in the evening before a trip.
They value a trusted, time-saving opinion over infinite choice, and they can tell a
reasoned recommendation from a sales pitch. Single user, local demo, English; the
backend may think for tens of seconds on real-model turns.

## Product Purpose

agentic-shop replaces the ecommerce page with a conversation. A shopping agent
searches a curated catalog, ranks products with a deterministic scorer, explains its
reasoning with real attribute values, and generates UI plans (result grids,
comparisons, preference chips, cart views) that render inside one transcript. Success:
the user goes search → refine → compare → recommend → cart entirely in the
conversation, and trusts the pick because every reason cites a checkable number.

## Brand Personality

**Confident curator**: assured, opinionated, editorial. The agent has taste and
states it — "this one, not that one, and here's why." Copy is short, declarative, and
attribute-grounded; numbers and reasons carry the persuasion, never hype adjectives.
The interface behaves like an expert personal shopper's desk: calm surface, decisive
ink.

## Anti-references

- **The AI-SaaS gradient** — purple-to-blue gradients, glassy blur cards, Inter
  everywhere, floating pill buttons, identical three-card feature rows.
- **Mall ecommerce** — dense coupon-energy grids, shouting buy-buttons, banner clutter.
- **Terminal dark neon** — monospace-as-personality, glow effects, hacker cosplay.
- **Cute consumer toy** — pastel blobs, emoji-heavy microcopy, mascot energy.

## Design Principles

1. **One recommendation at a time.** The agent commits; the UI underlines the commit.
   Emphasis is rare, so emphasis means something.
2. **Reasons over ads.** No persuasion without a number; every claim is traceable to
   a real product attribute.
3. **Paper, not glass.** The interface is a calm desk surface. Depth comes from ink
   weight and tonal steps, never from blur, glow, or stacked shadows.
4. **Calm is a feature.** Long agent thinking is normal; waiting must feel like work
   being done, not loading being suffered.
5. **Craft is the brand.** Spacing, type, and focus-state precision are the visible
   product; the anti-slop stance is strategic, not decorative.

## Accessibility & Inclusion

WCAG 2.2 AA basics are mandated (labels, focus visibility, keyboard access, semantic
regions, contrast, reduced motion). Streaming answer text must be screen-reader
considerate (polite live region, terminal announcements). Long-latency states need
honest, non-anxious progress indication.
