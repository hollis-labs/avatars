# avatar_generate — contract (as shipped in the Station avatar-server, model side)

Status: updated 2026-10-14 to match what shipped. The Station `avatar-server` (apps/station, plugins/avatar-server) wraps
`avatar.py` as its `image` and `hybrid` modes. **The server owns** the tool contract, the 16-slot palette registry, the
file store, fallback policy and spend limits. **This repo owns** the model call, palette snap, downscale and despeckle.
Sections marked *(server)* describe server behaviour as reported by the Station agent; the CLI sections are authoritative here.

## Principles
1. **The stored file is the source of truth.** Model output is not reproducible, so idempotence = "file exists → return it, no generation" unless `force`.
2. **Never fail when a cheaper path exists.** Model modes fall back to the procedural SVG per the configured policy chain.
3. **Cost and secrets are gated.** The model path needs a credential and spends money; both are checked before any call.
4. **Same name in, same file out.** Filename = URN name, NFC-normalized, path-hostile characters replaced.

## Tool request *(server)*
| field | type | default | notes |
|---|---|---|---|
| `urn` | string | required | URN name; also the file stem |
| `mode` | `svg` \| `image` \| `hybrid` | `hybrid` | svg = procedural sprite; image = model + golden ref; hybrid = model + golden ref + the agent's sprite as identity ref |
| `fallback` | policy chain / `none` | per-mode chain: hybrid→svg, image→svg | a configured policy chain, not hard-coded; `none` fails loudly |
| `force` | bool | false | regenerate even if the file exists |
| `role`, `species`, `mood` | string | "" / `robot` / "" | model modes only |
| `palette` | slot name | registry slot | named curated slot |
| `accent`, `bg` | `#RRGGBB` | from slot | explicit colours (split from the old combined `palette` override) |
| `budget_usd` | number | server config | per-call ceiling |

Changes from the first draft: `out_dir` is **server config only** (a caller-chosen path would let an agent write anywhere); `palette` is split into `palette` (slot name) and `accent`+`bg`; `hue` is gone; `fallback` is a policy chain per mode; `fallback_detail` was added to responses; a read-only `avatar_status` tool was added; `svg` mode files are 64 px canonical with `native_grid: 8`; the sidecar keeps this repo's fields and the server adds its own under `"avatar"`.

## Tool response *(server)*
`requested_mode`, `used_mode`, `fallback_reason`, `fallback_detail`, `existed`, `files[]` (path, format, px, native_grid), `sidecar`, `provenance` (generator version, model, cost_usd, prompt hash, golden ref hash, identity ref hash, palette, despeckle, Hadron run id), `reproducible` (true only for svg).

## Error codes
Server: `over_budget`, `credential_missing`, `scope_missing`, `no_image`, `model_error`, `model_unconfigured`, `name_collision`, `registry_corrupt`, `spend_ledger_corrupt`, plus the earlier `budget_refused`/`invalid_urn` naming where used.
CLI (this repo) emits: `over_budget`, `credential_missing`, `scope_missing`, `no_image`, `model_error`, `ledger_corrupt`, `registry_corrupt`, `internal_error`. The server should map CLI `ledger_corrupt` → `spend_ledger_corrupt`.

## Spend limits *(server)*
Per-call, per-UTC-day and total, enforced against the server's own ledger. The CLI additionally enforces `AVATAR_SPEND_CAP` against its own `ledger.json` (defence in depth; it records each call's cost).

## CLI contract (public; changing any of this needs a heads-up to the server owner)
```
python3 -I avatar.py [--out=DIR] [--accent=#HEX] [--bg=#HEX] [--role=R] [--species=S] [--mood=M]
        [--identity-ref=PNG --ref-style=sprite|outline|mask] [--curated] [--model=M]
        [--force] [--dry-run] [--json] [--scratch=DIR] [--chunky] [--no-despeckle] -- <urn>
```
- Writes `<safe-name>.png` (64×64), `<safe-name>@8x.png`, `<safe-name>.json` into DIR. Sidecar keys: `urn, model, prompt, golden, identity_ref, palette, palette_name, ref_style, despeckle, grid, colors_used, cost_usd` (`chunky` only when set).
- Existing `<safe-name>.png` and no `--force` → no model call. With `--json` the line carries `"existed": true`, `"cost_usd": 0.0`, `"model": null`.
- `--json` success (stdout, one line): `{"png","png8x","sidecar","cost_usd","model"}` (+ `"existed":true`).
- `--json` failure (stderr, one line): `{"code","message","cost_usd"}`; exit status per class: `over_budget` 10, `credential_missing` 11, `scope_missing` 12, `no_image` 13, `model_error` 14, `ledger_corrupt` 15, `registry_corrupt` 16, `internal_error` 70 (argparse usage 2). `cost_usd` on failure is the billed cost (a provider answer with no image is billed: `no_image` carries it and it is in the ledger). Without `--json` the same classes print `error[<code>]: <message>` to stderr with the same statuses; the message keeps the old substrings (`budget cap reached`, `HTTP 401`, `no image returned`).
- HTTP mapping: 401 → `credential_missing`, 402 → `over_budget` (provider credits), 403 → `scope_missing`, other HTTP/network → `model_error`.
- Environment (read at call time, never at import; defaults unchanged): `AVATAR_KEY_FILE` (default `~/.config/avatars/avatar-openrouter`), `AVATAR_LEDGER` (default `ledger.json` beside the script), `AVATAR_SPEND_CAP` (default 9.50), `AVATAR_REGISTRY` (default `palette_registry.json` beside the script). The key is read only when a call is about to be made and is never printed or put in an error.
- `golden/robot-01.png` must exist. Scratch files (identity-ref images) go to a fresh temp dir (or `--scratch DIR`) and are removed after the call; nothing is written under `out/`.
- Identity ref: 512×512 RGBA PNG, 8×8 cells of 64 px, transparent background, sprite pixels opaque.
- Locking: `ledger.json` updates and `palette_registry.json` reads/writes hold an exclusive advisory `flock` on `<file>.lock`; another writer sharing the file (the Go server) must flock the same `.lock` path. Writes are atomic (`.tmp` + rename).
- Registry safety: a missing registry is empty; a present-but-unreadable or malformed one is **refused** (`registry_corrupt`), never overwritten. Same for the ledger (`ledger_corrupt`).

## Palette registry
16 curated (accent, bg) pairs, slot assigned at first use, persisted. Start at `sha256(NFC urn)[0:2] % 16`, probe forward past taken slots → collision-free for the first 16 ids; beyond 16 slots are shared. Assignment depends on first-use order, so the registry file is authoritative. Same table and slot arithmetic in the server and in `curated_pair` (verified identical on 20 names).

## Model pipeline
golden ref (+ recoloured 8×8 sprite for hybrid) → model (default `google/gemini-3.1-flash-lite-image`, ≈ $0.034/image) → snap to the per-agent palette at 256 px → block-mode downscale to 64×64 → despeckle → write files.
Despeckle (two rules, up to 3 passes): (1) an isolated pixel that is a near shade of its neighbours' majority colour takes it; (2) a ≤2-pixel same-colour component, outside the outline-dark/highlight-white luma band, takes the majority colour of its surrounding ring if that holds ≥60 % of the ring.

## Findings that affect callers (2026-10-14, ~$0.35 of model calls)
- **Reference style:** `sprite` holds identity best. Silhouette overlap with the 8×8 sprite (mean over 6 agents): sprite IoU 0.71 / top-profile match 0.92; outline 0.69 / 0.88; mask 0.60 / 0.62 (mask's gizmo run is partly a metric artifact: a dark head that matches the bg family; excluding it mask ≈ 0.68 / 0.75). `outline` has visible failure modes (jagged halo, literal ear squares). One sample per cell, so treat differences as small. Keep `sprite` as the default.
- **Accessories:** `--chunky` (opt-in prompt addition: large, simple, ≥8 px accessories fully inside the frame) visibly retains quills, magnifiers and headsets that the baseline shrinks to blobs at 64 px. Recommended whenever `role` is set.
- **Speckle:** rule (2) removes a further 17–28 px per avatar on existing outputs (chin/hand specks); larger model-drawn colour patches are regions, not specks, and stay.

## Open questions
1. Real mail-URN format (sanitizer is lossy for `/`, `:`; `a/b:c` and `a_b_c` collide; the server reports `name_collision`).
2. Gateway image path untested (`ai.invoke` scope missing in the test session). If it works, model modes should use it and drop the raw key.
3. Procedural side latency (~2 s to `succeeded` vs 90–200 ms run).
4. Golden sample governance: one golden per silhouette family?
5. Whether the key file is `avatar-openrouter` (this machine) or `avatars-openrouter` (Station machine, symlinked): the default is unchanged; set `AVATAR_KEY_FILE`.
