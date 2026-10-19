# Changelog

## Unreleased

- Public repository: README, licence, contributing and security notes, and CI.
- `ledger.json` is local state and is no longer tracked.

## 0.2.0

- `--json` output and a distinct exit status per failure class, for the Station avatar server.
- Despeckle v2: isolated near-shade pixels and small same-colour components take their surroundings' colour.
- `AVATAR_KEY_FILE`, `AVATAR_LEDGER`, `AVATAR_SPEND_CAP` and `AVATAR_REGISTRY` overrides; advisory locking of the
  ledger and registry; a corrupt ledger or registry is refused rather than overwritten.

## 0.1.0

Initial import: the 8-bit agent avatar generator and its experiments.
