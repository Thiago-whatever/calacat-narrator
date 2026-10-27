# Design

The visual system and the Reporter console spec. The interactive prototype lives on a private Claude design canvas ([Calacat Reporter Console](https://claude.ai/artifact/6xnGg1T13X8nrSbZu8ecFk)); this document is the source of truth when the two disagree. Decisions are ADR-031 to ADR-035 in [decisions.md](decisions.md).

All teams, players and matches in the prototype are fictional demo data.

## Look

Clean, premium, editorial. The starting point was the "Agence Foudre" style reference (cream canvas, deep green text, magenta accent, condensed display type). We keep its palette and type pairing but adapt it for a dense, live control room (ADR-031).

### Color tokens

| Token | Value | Role |
| --- | --- | --- |
| `--bg` | `#fff8f6` | Page canvas (warm chalk) |
| `--surface` | `#ffffff` | Panels, feed cards, buttons |
| `--tint` | `#fce5df` | Pills, soft fills, hover |
| `--ink` | `#00522d` | All body text and icons (forest green, never black) |
| `--ink2` | `#3d6b55` | Secondary text, labels (5.9:1 on `--bg`) |
| `--line` | `#efd9d3` | Borders, dividers |
| `--brand` | `#c0256f` | Primary action (Go live), focus ring, accents. Darkened from `#db3c8a`, which fails 4.5:1 with white text |
| `--live` | `#d7261e` | Live / on-air state only |
| `--grey` | `#6b6b6b` | Preview state badge |
| `--stage` | `#0f2a1c` | Program monitor background |
| Bubblegum | `#f29ebd` | Decoration only: drop targets, guides, kick-off title. Never text on light |

High-contrast mode swaps the tokens to black on white, `--brand` to `#7d0a43` and `--live` to `#b00000`.

### Team colors (demo)

| Team | Short | Color | Ink | Soft |
| --- | --- | --- | --- | --- |
| Ríos FC | RÍO | `#1e5bb8` | `#ffffff` | `#dbe7fb` |
| Atlético Norte | NOR | `#c2540a` | `#ffffff` | `#fbe3d2` |
| Puerto Sol | SOL | `#f2c230` | `#1a1a1a` | `#fdf1c6` |
| Valle Real | VAL | `#6b3fa0` | `#ffffff` | `#e8dff4` |

Pairs are chosen to differ in lightness as well as hue (blue/orange, yellow/purple). Team color appears **only** in the player silhouette or team shield on a card, and in the score bug (ADR-035). The team is always also named in text.

### Type

- **Display:** Antonio 700, uppercase, line-height 0.95. Headlines, the countdown digit, the brand name. Never below ~20px.
- **UI and body:** Instrument Sans 400/500/600/700. Everything functional.
- Base size 15px; "Larger text" mode raises it to 17px. All sizes are in `em` so the whole console scales.

### Shape and depth

- Radii: 10px buttons, 14px large buttons and segments, 18–20px panels and cards, full round pills.
- Flat. No gradients or glass. The only shadows are the red live ring and the selected-card inset ring.
- Touch targets ≥ 44px; the control bar uses 56px.

## Reporter console

One screen with no page scroll on desktop (ADR-032). Below ~1100px wide or ~560px tall it stacks into one scrolling column.

```text
┌───────────────────────────────────────────────────────────────────────┐
│ ● Calacat Narrator             [▶ Start match] [English ▾] [♿ Access.] │
│ ─────────────────────────────────────────────────────────────────────  │
│ TRANSMISSION  [● TV 1  RÍO 1–0 NOR] [TV 2  SOL 1–1 VAL] [Stream …] 1st │
├───────────────────────────────────────────┬───────────────────────────┤
│                                           │ INSIGHT FEED      8 cards │
│        Program monitor (16:9)             │ [All] [RÍO–NOR PGM] [SOL…]│
│   score bug · output tally · pitch        │ Focus [No focus      ▾]   │
│   on-screen card (preview / live)         │ ┌───────────────────────┐ │
│                                           │ │ card                  │ │
├───────────────────────────────────────────┤ └───────────────────────┘ │
│ ● Status  Size [S M L]  [■ Pull]  [◉ Go live]│ …feed scrolls             │
└───────────────────────────────────────────┴───────────────────────────┘
```

The monitor's width is capped by viewport height (`(100vh − 284px) × 16/9`) so the monitor and control bar always fit; the feed takes the rest and scrolls inside its own column.

### Header

- Brand, then **Start match / Pause / Resume / Restart** (demo only: drives the simulated clock), language (English / Español), and an **Accessibility** popover (high contrast, larger text, reduce motion, shortcut list).
- Second row: the **Transmission** switcher (ADR-034). One button per output with its name, its match score, and a dot that blinks red when that output has a card on air. Followed by the period pill (Pre-match / 1st half / 2nd half / Full time). Switching is disabled during a countdown.

### Program monitor

- Stand-in for the selected output's video: striped grass and a regulation pitch drawn in SVG to real proportions (both penalty areas, six-yard boxes, spots, arcs, goals, center circle, corner arcs).
- Score bug top-left in the two teams' colors with the match minute; output tally top-right (`TV 1`, red `TV 1 · On air` when live).
- Before kick-off: "Kick-off soon" in bubblegum display type.

### On-screen card

Content only: silhouette or shield, a "who" line (`#9 Rivas` or the team name), headline, body. No header strip. A small state badge floats above the card's top-left corner.

| State | Look | Badge | Interaction |
| --- | --- | --- | --- |
| Preview | Grey card (`#ececec`), dashed grey outline; silhouette keeps team color | `PREVIEW` (grey) | Drag anywhere, edit text in place, resize, × to remove |
| Countdown | Normal card, solid red outline | `LIVE IN 3` (red) | None; cancel from the control bar |
| Live | Normal card, solid red ring plus a red ring pulsing outward (recording light) | `● LIVE` (red, blinking) | **Locked.** No ×, no handles, no editing. Only Pull from air |

Preview editing:

- **Place:** drag the card anywhere inside the monitor; it snaps to the horizontal center with a dashed guide. Keyboard: the move button (bottom-left corner) with arrow keys, Shift for 10% steps.
- **Edit:** click the headline or body to type in place (headline ≤ 60 chars, Enter finishes; body ≤ 180 chars). A press that moves becomes a drag instead.
- **Resize:** right-edge bar (width), bottom-edge bar (height), corner dot (both). Width 22–70% of the monitor, height 14–80%, never past the edge. Arrow keys on each handle. Text scales with width.
- **Remove:** × on the top-right corner clears the preview (does not touch what is on air).

Geometry is stored as percentages of the monitor (`x`, `y`, `width`, optional `height`) so it maps to any output resolution.

### Control bar

Always directly under the monitor, never moves.

- Status light and text: `Off air · TV 1` → `Preview · not live` → `Going live on TV 1 · 4s` → `On air · TV 1 · 0:42`.
- **Size** S / M / L (30 / 40 / 56% width, auto height).
- **Pull from air** (outlined, 56px). Acts on the selected output.
- **Go live on *output*** (magenta, 56px, `Enter`). Becomes **Replace on *output*** when that output already has a card.
- During the countdown both buttons are replaced by **Go live now** and **Cancel** (`Esc`), with a red bar draining over 5 seconds (ADR-033).

A success toast ("Card is live on TV 1", with Pull) appears bottom-right over the feed for 4 seconds when the countdown completes.

### Insight feed

- Ranked by Editor salience. New cards pop in with a short spring; the newest has a `New` pill.
- **Game filter** chips: All games, then one chip per match with its live score and count; the chip for the selected output's match carries a `PGM` tag.
- **Focus** select (teams and players): when set, the feed shows **only** cards about that team or player (ADR-034).
- Card anatomy: neutral team chip, topic pill (goals in magenta), minute, `New` / `Live · TV 1, Stream` pills; silhouette with jersey number (player cards) or team shield (team cards); player line; headline; body; specialist name, match score (in All games), salience bar with the number.
- Click previews the card on the monitor; drag it with a ghost onto any point of the monitor. A card that is live on the selected output is locked (not clickable or draggable, `aria-disabled`).

### Getting started

- An **ⓘ How it works** button sits after the Accessibility button. It opens a dialog explaining the demo (scripted, in the browser, instant) and, when the API is configured, the live match (simulated on the server, written by the agents, first cards within a minute), followed by the four steps to put a card on air. It opens by itself on a first visit only (remembered per browser); Esc or **Got it** closes it.

### On-air output

- **Open on-air output** opens `?overlay=<output>` in a new tab: what viewers of that transmission get, never an editing surface. The console is titled **Control room** so the two are never confused.
- Its title row says **On-air output · TV 1** with a **What viewers see** tag; the transmission switcher, **Back to control room** and the Accessibility menu sit on their own row below it, so a longer output name never moves them.
- A tally strip above the stage reads **ON AIR · TV 1** in red with the headline, or **OFF AIR · TV 1** in grey; the stage gets a red frame while on air. A note below repeats that nothing here can be edited.
- The output is always in English, whatever language the console uses: the page itself, and the card (the reporter's English edit if there is one, else the English text).

## Accessibility

Target WCAG 2.2 AA (see [accessibility.md](accessibility.md)).

- Every control is a real `button`, `select`, `input` or `textarea` with a visible 3px focus ring.
- Live regions: feed additions `polite`; goals `assertive`; countdown start, cancel, removal and pull announced `polite`; the success toast is `role="status"`.
- State is never color-only: every state has a text badge, and every team color has its name next to it.
- Silhouettes and shields have `role="img"` labels ("Player Rivas, Ríos FC, jersey number 9").
- Keyboard: `J` / `K` move through the feed, `Enter` on the selected card starts the countdown, `Esc` cancels the countdown, closes the popover, leaves a text field, pulls from air, or clears the preview, in that order.
- Reduce motion (toggle or OS setting) stops the pop-in, pulse and blink animations; the live ring stays solid.
- UI strings live in one table per language; cards are written per language (see accessibility.md).

## Motion

| Moment | Motion |
| --- | --- |
| Card arrives in feed | 450ms rise and fade, ease-out |
| Card appears on monitor | 400ms rise and fade |
| Live | Red ring expands and fades, 1.6s loop; badge dot blinks 1.2s |
| Countdown | Bar drains linearly over 5s |
| Drag from feed | Ghost tilts −2° and straightens over the drop target |

All of it is removed under reduce motion.
