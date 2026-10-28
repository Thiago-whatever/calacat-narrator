# Accessibility

The goal is that anyone can follow and understand the match, whatever language they speak, however they see, and however much football they know. The target is **WCAG 2.2 AA**. The console's detailed rules (focus rings, live regions, keyboard order, motion) are in [design.md](design.md#accessibility).

## Built

- **Language:** English and Spanish for both the interface and the cards. The UI strings live in one JSON file per language (`web/src/locales/`). Cards are written in English and translated by the Reviewer in the same call, with the same number check (ADR-040). Template cards have both languages too.
- **Screen readers:** new cards are announced in a `polite` live region and goals in an `assertive` one. The go-live countdown, cancel and pull are announced too. Silhouettes and shields have text labels.
- **Keyboard:** the whole reporter flow works without a mouse: J/K to move through the feed, Enter to start the 5-second go-live countdown, Esc to cancel it or pull from air.
- **Vision:** a high-contrast theme, larger text, and no meaning carried by color alone (every state has a text badge, and every team color has its name next to it).
- **Motion:** a reduce-motion setting, which also follows the OS's `prefers-reduced-motion`.
- These settings are remembered in the browser.

## Not built yet

| Idea | Issue |
|---|---|
| Fan mode: casual or analyst depth, favorite club or player | C15 |
| Audio narration of cards | C22 |
| Heatmaps and zone views, each with a text alternative | C21 |
| Portuguese and French | C34 |

## Test checklist

- [ ] axe DevTools: no serious or critical issues on the console and the on-air output
- [ ] NVDA announces new cards, and goal cards interrupt
- [ ] The full reporter flow works keyboard-only
- [ ] 200% zoom with no horizontal scroll
- [ ] Reduce motion is honored
- [ ] Spanish output reviewed by a native speaker
