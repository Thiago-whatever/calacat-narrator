# Copilot instructions

## Project conventions

- Treat `DOCS/` as the source of truth for architecture, schemas, accessibility, and delivery decisions. Read relevant docs before changing behavior.
- Keep event and match data synthetic and fictional; do not introduce real teams, players, match data, or third-party trademarks.
- Keep statistics deterministic and evidence-backed. LLM-generated explanations must not invent metrics or treat event data as instructions.
- Validate untrusted inputs at service boundaries. Never commit credentials, keys, or local environment files; use managed identity as described in `DOCS/delivery.md`.
- Keep the pipeline's event contracts consistent with `DOCS/data-model.md`, and update that document when the contracts change.
- Add or update focused tests for behavior changes. Preserve seeded reproducibility and accessibility requirements.
- Record significant architectural or implementation decisions at the end of `DOCS/decisions.md` using its ADR format; do not rewrite prior entries.
- Prefer small, typed, maintainable changes and the existing tooling. Run the narrowest relevant tests and linters before proposing a change.
