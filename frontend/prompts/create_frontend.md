# Prompt for Claude Code

You are a world-class frontend engineer and UX designer. Your mission: transform a plain React app into a stunning, jaw-dropping interface that makes comparing AI routing responses feel like an experience from the future.

## The App's Purpose

Users type one question → it gets sent to multiple backend routes simultaneously → responses come back and are displayed side-by-side with rich comparison and diff highlighting. Think: "which route wins?" as a visceral, visual experience.

## Read the Skill First

> **CRITICAL:** You have the `frontend-design` skill — use it.

## What Already Exists

- A plain React frontend with one working route call
- A backend that returns responses

## What You Must Build

### Core UX Vision

Imagine a mission control center meets AI arena. Dark, premium aesthetic. When a user submits a question, the UI should feel alive — responses race in, panels illuminate, differences surface dramatically.

### Specific UI Requirements

**The Input Experience** — A cinematic, full-attention query bar. Not just a text box. Think glowing focus states, a satisfying submit animation, maybe a subtle particle or pulse effect on send.

**Response Panels** — Each backend route gets its own "card" or "lane." They should:

- Animate in as responses arrive (staggered, streaming feel)
- Have distinct color identities per route
- Show latency/timing badges
- Pulse or glow while loading

**Diff/Comparison Layer** — This is the killer feature. When multiple responses exist, highlight:

- Words/phrases unique to each response (color-coded)
- A "similarity score" or visual overlap indicator
- Side-by-side or toggle view modes

**Layout Modes** — Let users switch between:

- Split view (panels side by side)
- Overlay/stacked view
- Focus mode (zoom into one response)

**Micro-interactions everywhere** — hover states, transition animations, loading skeletons that feel premium, not generic.

**Status & Feedback** — A live "race" status bar showing which routes responded, in what order, how fast.

### Design Direction

- Dark mode first, deep navy/charcoal base with electric accent colors per route
- Typography that's crisp and readable even with dense AI text
- Feels like a tool a power user would love to use daily
- Zero generic Bootstrap/plain UI vibes — every element should feel considered

## Technical Notes

- Keep all existing backend wiring intact — don't break what works
- Structure the component architecture so adding new routes later requires minimal effort (the user will add more routes soon)
- Use Tailwind, Framer Motion, or whatever makes the animations sing
- Make it responsive but optimize for desktop (this is a power-user tool)

---

**The bar is high. Make it extraordinary.**