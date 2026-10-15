# avatars

Idempotent 8-bit agent avatar generator (experimental). See `docs/CONTRACT.md` for the merge contract.

    python3 -I avatar.py <urn-name> [--role R] [--species S] [--mood M] [--accent #hex] [--bg #hex]
                         [--curated] [--identity-ref sprite.png --ref-style sprite|outline|mask]
                         [--model M] [--out DIR] [--force] [--dry-run]
    python3 -I serve.py 8765        # review UI: http://127.0.0.1:8765

- Existing `<out>/<name>.png` => no model call. `--force` regenerates.
- Key: `~/.config/avatars/avatar-openrouter` (never printed). Spend ledger: `ledger.json`, hard stop in `lib.py`.
- `--curated` assigns a palette slot from `palette_registry.json` (first-use, collision-free up to 16 ids).
- Experiments: `exp1-3.py`; outputs in `out/` (e1-e3 raw/post, `agents/`, `compare/`, `theirs/`, `hybrid/`, `h2-*`).
