# Accessibility and empowerment

The goal is that every fan can follow and *understand* the match, whatever language they speak, however they see, and however much football they know. Target: **WCAG 2.2 AA**.

## Language
- EN + ES at launch, with PT/FR as stretch. The agent writes natively in the target language instead of translating after the fact, and output is cached per `(card, lang, depth)`.
- The UI strings are in a single JSON per language.

## Visual impairment
- The card feed is an ARIA live region: `polite` for normal cards, `assertive` for goals, red cards and penalties.
- **Audio narration mode:** Azure AI Speech neural voices read cards in the user's language.
- **Every chart has a text alternative**, generated from the same data ("Heatmap: Rivas spent 41% of the first half in the left half-space").
- High-contrast theme, a colorblind-safe palette, and no meaning carried by color alone.
- The reporter flow works keyboard-only: J/K to move, Enter to start the 5-second go-live countdown, Esc to cancel it or pull from air (see [design.md](design.md)).

## Cognitive and low vision
- Respects `prefers-reduced-motion`, and cards don't auto-scroll while focused.
- Font scaling up to 200% without loss of content.
- **"New to football" depth:** terms such as "half-space" or "inverted fullback" are defined inline.

## Empowerment
- An **"Explain this stat"** button on each metric shows how it's computed, in plain language.
- The **public MCP server** lets anyone plug in their own agent.
- An open-source repo with these docs and a data dictionary (data-model.md).
- A text-only low-bandwidth mode.

## Test checklist
- [ ] axe DevTools: no serious or critical issues on Reporter, Overlay, Fan
- [ ] NVDA announces new cards, goal cards interrupt
- [ ] Full reporter flow works keyboard-only
- [ ] 200% zoom, no horizontal scroll
- [ ] Reduced motion honored
- [ ] ES output reviewed by a native speaker
