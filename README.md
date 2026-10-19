# avatars

A small Python tool that draws 8-bit pixel-robot avatars for agents with an image model, then snaps them to a fixed
palette and downscales them to a crisp 64×64 sprite. It is the *model path* of the Hollis Labs avatar service: the
[`station-avatar-server`](https://github.com/hollis-labs/plugins/tree/main/station-avatar-server) plugin owns the tool
contract, the shared palette registry, the file store, fallback policy and spend limits, and calls this tool for its
`image` and `hybrid` modes.

> **Experimental.** The command-line contract in [`docs/CONTRACT.md`](docs/CONTRACT.md) is stable because a server
> depends on it. Everything else (the experiment scripts, the review viewer, the prompts) is a working notebook.

## What it does

- **Idempotent.** An existing `<out>/<name>.png` means no model call. `--force` regenerates.
- **Palette-locked.** Output uses the agent's accent and background plus a fixed outline and grey ramp. `--curated`
  assigns one of 16 curated pairs on first use and remembers it (`palette_registry.json`).
- **Style-matched.** A golden reference image (`golden/robot-01.png`) pins the house style. In `hybrid` mode the model
  is also shown the agent's own 8×8 sprite (`--identity-ref`, `--ref-style sprite|outline|mask`) so each agent keeps
  a recognisable silhouette.
- **Cost-gated.** Every call is recorded in a spend ledger and refused past a hard cap (`AVATAR_SPEND_CAP`, default
  $9.50). The credential is read only when a call is about to be made and is never printed.
- **Machine-readable.** `--json` prints one line on success, or a `{code, message, cost_usd}` line on stderr with a
  distinct exit status per failure class.

## Quick start

```sh
pip install -r requirements.txt

# See the prompt without spending anything.
python3 -I avatar.py --dry-run -- my-agent

# Draw one. Needs an OpenRouter key in ~/.config/avatars/avatar-openrouter (or AVATAR_KEY_FILE).
python3 -I avatar.py --curated --role builder --out ./avatars -- my-agent
```

Options: `--role`, `--species`, `--mood`, `--accent #hex`, `--bg #hex`, `--curated`, `--identity-ref PNG`,
`--ref-style`, `--model`, `--out DIR`, `--force`, `--dry-run`, `--json`, `--chunky`, `--no-despeckle`. Run
`python3 avatar.py --help` for the full list.

It writes `<name>.png` (64×64), `<name>@8x.png` (512×512) and `<name>.json` (provenance: model, prompt hash, palette,
cost).

## Configuration

Read at call time, never at import.

| variable | default | |
|---|---|---|
| `AVATAR_KEY_FILE` | `~/.config/avatars/avatar-openrouter` | file holding the provider key |
| `AVATAR_LEDGER` | `ledger.json` beside the script | spend ledger; point it outside the checkout |
| `AVATAR_SPEND_CAP` | `9.50` | hard stop on total spend, in dollars |
| `AVATAR_REGISTRY` | `palette_registry.json` beside the script | palette slot assignments; keep and back it up |

## Review viewer

`python3 -I serve.py 8765` serves a local page for comparing runs under `out/` at `http://127.0.0.1:8765`. It binds
to loopback only.

## Layout

```
avatar.py        the CLI
lib.py           model call, palette snap, downscale, despeckle, ledger, locking
prompts.py       prompt text
golden/          the style reference
docs/CONTRACT.md the CLI contract and what the server owns
exp1-3.py        experiments; their output is in out/
serve.py, viewer.html   local review viewer
```

`out/` holds the experiment output the findings in `docs/CONTRACT.md` came from. It is reference material, not
something the tool needs.

## Where it sits

```
  agents / browsers
        │  MCP (token)        HTTP (read-only)
  station-avatar-server  ──  svg engine (native Go, free)
        │  image / hybrid
     avatar.py  ──►  image model (paid, not reproducible)
```

The procedural `svg` mode, previews and the browser endpoints live in the server, not here.

## License

MIT. See [`LICENSE`](LICENSE).
