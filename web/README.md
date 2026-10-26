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
- **Live**: build with `VITE_API_BASE_URL=/api` (see `.env.example`) and open `/?match=m-0007`.
  The console calls `GET /api/negotiate`, connects to the receive-only Web PubSub URL, then loads `GET /api/cards`
  (unexpired cards plus the interpreter's score) on every connect and every 30 s. Cards are deduplicated by `card_id`,
  and expired ones leave the feed and can't be sent to air.
  Teams and players come from the backend catalog in `src/calacat_narrator/data/`.

## Hosting

Static Web Apps with the Function App as a linked backend (ADR-036), so `/api/*` is same-origin.
`public/staticwebapp.config.json` restricts the whole console (and `/api/*` through it) to the `reporter` role,
redirects anonymous users to sign in, and sets a CSP that allows only `'self'` and `wss://*.webpubsub.azure.com`.
Fonts are bundled from `@fontsource`, so the page makes no third-party requests.

## Deploy (GitHub Pages)

`.github/workflows/deploy-web.yml` lints, tests, builds and publishes `web/` on every push to `main` that touches it (or on demand from the Actions tab).
The site is served at `https://<owner>.github.io/<repo>/`; the workflow passes that base path to the build.

One-time setup:

1. The repository must be public (GitHub Pages on a free plan; the hackathon rules also require it).
2. **Settings → Pages → Source: GitHub Actions.**
3. Optional live mode: add the repository variable `VITE_API_BASE_URL` (Function App origin) and allow `https://<owner>.github.io` in the Function App's CORS.

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
