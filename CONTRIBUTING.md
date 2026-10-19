# Contributing

`README.md` has the setup; `AGENTS.md` is the fastest orientation to the layout and the boundaries that are not
obvious from reading the code.

1. **Branch** as `<type>/<short-slug>` (`feat`, `fix`, `docs`, `chore`) and change one thing.
2. **Check.** `python3 -m py_compile avatar.py lib.py prompts.py serve.py`, then
   `python3 -I avatar.py --dry-run --json --out "$(mktemp -d)" -- ci-check`. Neither spends money or needs a key.
3. **Judge model changes by output.** There is no test suite. Show the before and after images and the cost from the
   ledger, and say how many samples they are.
4. **Mind the contract.** If you touch a flag, a `--json` shape, an exit status or an environment variable, update
   `docs/CONTRACT.md` in the same change; a server depends on it.
5. **Keep secrets and local state out.** No keys, no `ledger.json`, no `palette_registry.json`.

Open a pull request against `main` describing what changed and why.
