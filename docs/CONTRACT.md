# avatar_generate — proposed tool contract (model side)

Status: DRAFT for merge with the Hadron-side avatar MCP server. Written 2026-10-14 from the experiments in this repo.
Companion to the procedural side's proposal (`mode` enum, hybrid default, fallback to svg).

## Principles
1. **The stored file is the source of truth.** Model output is not reproducible, so idempotence = "file exists → return it, no generation" unless `force`.
2. **Never fail when a cheaper path exists.** Model paths fall back to the procedural SVG unless `fallback: "none"`.
3. **Cost and secrets are gated, not assumed.** The model path needs a credential and spends money; both are checked before any call.
4. **Same name in, same file out.** Filename = URN name, NFC-normalized, path-hostile characters replaced.

## Request
| field | type | default | notes |
|---|---|---|---|
| `urn` | string | required | URN name; also the file stem |
| `mode` | `svg` \| `image` \| `hybrid` | `hybrid` | svg = procedural sprite; image = model + golden ref; hybrid = model + golden ref + the agent's procedural sprite as identity ref |
| `fallback` | `svg` \| `none` | `svg` | what to do if the requested model path cannot run |
| `force` | bool | false | regenerate even if the file exists (new face; old file is kept as `<name>.<timestamp>.png`) |
| `role`, `species`, `mood` | string | "" / `robot` / "" | optional prompt variation (model modes only) |
| `palette` | slot name \| `{accent,bg}` | registry slot | explicit override |
| `budget_usd` | number | tool config | per-call ceiling; call refused if the estimate exceeds it |
| `out_dir` | path | tool config | |

## Response
```
{
  "requested_mode": "hybrid", "used_mode": "svg",
  "fallback_reason": "credential_missing | scope_missing | over_budget | model_error | null",
  "existed": false,                        // true => nothing generated, nothing spent
  "files": [ {"path","format":"png|svg","px":64,"native_grid":64,"role":"canonical|upscaled"} ],
  "sidecar": "<name>.json",
  "provenance": {
    "generator_version", "model", "cost_usd", "prompt_sha256",
    "golden_ref_sha256", "identity_ref_sha256", "palette": {"slot","accent","bg","colors":[...]},
    "despeckle": true, "hadron_run_id": "<svg/hybrid only>"
  },
  "reproducible": false                    // true only when used_mode == svg
}
```

## Fallback order
- `hybrid` → `svg` (the sprite already exists, it is the hybrid's identity input).
- `image` → `svg`.
- `fallback: "none"` → error instead, with the same `fallback_reason` code.
- Triggers: no credential, credential lacks the needed scope (today: gateway `ai.invoke`), estimated cost over budget, provider error/timeout, response without an image.
- The fallback is recorded in the sidecar so a later `force` knows the file is a stand-in; a stand-in file is **upgradable**: `mode=hybrid` on a file whose `used_mode` was `svg` because of a fallback regenerates without `force`.

## Palette registry
- 16 curated (accent, bg) pairs; slot assigned at first use, persisted in `palette_registry.json` (commit it). Start at `sha256(NFC urn) % 16`, probe past taken slots → no collisions for the first 16 ids; beyond 16 slots are shared.
- Assignment depends on first-use order, so the registry is authoritative; losing it can reassign colours.
- Both generators should read the same table so svg/image/hybrid of one agent share colours. Open question: where the table lives (shared lib vs registry service).

## Pipeline (model modes)
golden ref (+ recoloured 8x8 sprite for hybrid) → model (default `gemini-3.1-flash-lite-image`, ≈ $0.034/image) → snap to per-agent palette at 256px → block-mode downscale to 64×64 → despeckle → write `<name>.png` (64×64 canonical), `<name>@8x.png`, `<name>.json`.

## Errors
`budget_refused`, `credential_missing`, `scope_missing`, `model_error`, `no_image`, `invalid_urn`, `registry_locked`. All carry `requested_mode`, `used_mode: null`, and whether a fallback was attempted.

## Open questions
1. Real mail-URN format (sanitizer is lossy for `/`, `:`; `a/b:c` and `a_b_c` collide).
2. Gateway image path: untested (`ai.invoke` scope missing in the test session). If it works, model modes should use it and drop the raw key.
3. Per-image latency of the procedural side (~2 s to `succeeded` vs 90–200 ms run) — matters for a synchronous tool.
4. Golden sample governance: who adds/approves goldens, and is one golden per silhouette family needed?
5. Whether `svg` output should also get the curated palette (it currently seeds its own hue).
