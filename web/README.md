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

## Structure

Built on MUI (Material UI) with Emotion. All styling flows from one theme; no stylesheet files.

| Path | What |
| --- | --- |
| `src/theme/tokens.ts` | Design tokens: colors (normal + high contrast), fonts, radii, sizes, motion, breakpoints. The only place raw colors live |
| `src/theme/theme.ts` | `createAppTheme(prefs)`: MUI palette, typography variants (`display`, `label`, `hint`), custom Button/Chip variants and sizes, component overrides |
| `src/theme/AppThemeProvider.tsx` | Theme, CssBaseline and the global reduce-motion rule |
| `src/components/ui/` | Reusable kit: `Pill`, `StatusDot`, `KeyHint`, `SalienceMeter`, `EmptyState`, `SelectField`, `SegmentedControl`, `Toast`, icons |
| `src/components/{header,monitor,control,feed,layout}/` | Console features composed from the kit |
| `src/hooks.ts` | `usePrefs`, `useNow`, `useFeedDrag` |
| `src/state.ts` | Console reducer: preview, 5 s go-live countdown, on-air lock, pull (ADR-032/033/034) |
| `src/data/` | Demo fixtures and simulated clock; live Web PubSub adapter |
| `src/i18n.ts` | EN/ES UI strings |

To restyle, change tokens or theme overrides; components read `theme.custom.*` and never hard-code colors.
High contrast, larger text and reduce motion rebuild the theme from the same tokens.

Go-live state is local to the browser for now; the overlay delivery contract is C14.
