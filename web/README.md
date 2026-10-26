# Reporter console

React + TypeScript (Vite) implementation of the Reporter console in [DOCS/design.md](../DOCS/design.md).

```bash
npm install
npm run dev      # http://localhost:5173
npm test         # reducer and live-card parser
npm run lint
npm run build    # static site in dist/
```

## Modes

- **Demo** (default): the fictional fixtures from the design prototype, driven by **Start match**.
- **Live**: build with `VITE_API_BASE_URL` set to the Function App origin (see `.env.example`) and open `/?match=m-0007`.
  The console calls `GET /negotiate`, connects to the receive-only Web PubSub URL, and deduplicates cards by `card_id`.
  Teams and players come from the backend catalog in `src/calacat_narrator/data/`.
  The Function App must allow the console's origin in CORS.

## Layout

| Path | What |
| --- | --- |
| `src/state.ts` | Console reducer: preview, 5 s go-live countdown, on-air lock, pull (ADR-032/033/034) |
| `src/data/` | Demo fixtures and simulated clock; live Web PubSub adapter |
| `src/components/` | Header, program monitor, on-screen card, control bar, insight feed |
| `src/i18n.ts` | EN/ES UI strings |
| `src/styles.css` | Design tokens and layout; stacks below 1100px wide or 560px tall |

Go-live state is local to the browser for now; the overlay delivery contract is C14.
