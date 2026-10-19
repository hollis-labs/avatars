# avatars

The model path of the Hollis Labs avatar service: a Python CLI that draws a palette-locked 8-bit pixel-robot avatar
with an image model. It is not the avatar server. The tool contract, the shared palette registry, the file store,
fallback policy, spend limits, svg engine, previews and HTTP surface belong to the `station-avatar-server` plugin in
`hollis-labs/plugins`.

## Start Here

- `README.md` covers what the tool does, how to run it and its configuration.
- `docs/CONTRACT.md` is the CLI contract the server depends on, plus the pipeline and findings.
- `avatar.py` is the CLI; `lib.py` holds the model call, palette snap, downscale, despeckle, ledger and locking.
- `golden/robot-01.png` is the style reference; the tool refuses to run without it.

## Commands

```sh
pip install -r requirements.txt
python3 -m py_compile avatar.py lib.py prompts.py serve.py       # what CI checks
python3 -I avatar.py --dry-run --json --out "$(mktemp -d)" -- ci-check   # prompt only, no key, no spend
python3 -I serve.py 8765                                          # local review viewer
```

There is no test suite. A change to model behaviour is judged by looking at output and the ledger, not by assertion.

## Boundaries

- The CLI contract in `docs/CONTRACT.md` (flags, `--json` shapes, exit statuses, environment, sidecar keys) is depended
  on by the server. Changing any of it needs the server's owner told first, and the contract updated in the same change.
- The key file is read only when a call is about to be made and is never printed or put in an error message.
- Spend is capped and recorded. Do not weaken the ledger, its lock or the cap to make a run pass. Keep
  `ledger.json` and `palette_registry.json` out of commits: both are local state.
- A present but unreadable or malformed ledger or palette registry is refused, never overwritten. Overwriting a
  registry silently reassigns every agent's colours.
- Scratch images go to a temp directory and are removed after the call; nothing is written under `out/` by the CLI.
- This repository is public. Nothing secret, no token, internal host name, internal address or personal path may enter a
  file, a commit message or CI config. Documentation names only things a stranger can see here or on the public Hollis
  Labs organization.

## Do Not

- Add a `CLAUDE.md`; `AGENTS.md` is the single instruction file.
- Commit a key, a ledger or a registry.
- Run the model path in a loop or in CI. It costs money and is not reproducible.
