# Security policy

## Supported versions

This is an experimental tool. Fixes are made on `main`.

## Report a vulnerability

Do not put a key, token, ledger or other sensitive material in a public issue. Use GitHub's private
vulnerability-reporting flow when the repository's Security tab offers it; otherwise contact a maintainer privately
through a channel published on the Hollis Labs organization or maintainer profile. Include the affected commit, what
you did, and the impact.

## What matters here

- The provider key is read from a file on demand and must never be printed, logged or put in an error or sidecar.
- The tool spends money. A way to exceed or bypass the spend cap, or to make the ledger or registry accept
  attacker-controlled content, is a vulnerability.
- Agent names become file names; a way to write outside the output directory is a vulnerability.
- `serve.py` is a local review viewer and binds to loopback only. It is not meant to be exposed.
