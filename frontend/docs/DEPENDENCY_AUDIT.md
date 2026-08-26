# Frontend dependency audit — reachability triage

`npm audit --omit=dev` on this branch (lockfile SHA-256
`d4418865b05858a869d56e704e2d3b01c62eac42d5c3c4c1248cab4b1ee5431f`)
currently reports 26 findings (12 high, 14 moderate, 0 critical). An
external audit against the same commit reported 92 (76 high, 16
moderate) — same lockfile, same resolved dependency count (902), but a
different live npm-registry advisory snapshot. Treat neither raw count as
stable; `npm audit`'s numbers are a live registry query, not a property
of the lockfile. What follows is a reachability read of the packages
actually named, which doesn't depend on which snapshot you hit.

## Finding: every flagged package traces to Expo/Metro build tooling

All 26 findings resolve to six root vulnerable packages, everything else
in the report is just the dependency chain carrying them:

| Root package | Issue class | Reached via |
|---|---|---|
| `postcss` | XSS in CSS stringify output; arbitrary file read via `sourceMappingURL` | `@expo/metro-config` (Metro's CSS pipeline) |
| `image-size` | Infinite loop on malformed ICNS/JXL/HEIF | `metro`/`metro-transform-worker` (asset dimension probing during bundling) |
| `js-yaml` | Quadratic CPU on `!!omap` resolution | Expo config-plugin YAML parsing |
| `nanoid` | Non-secure generator can loop indefinitely with a bad `size` arg | Expo/Metro tooling internals |
| `brace-expansion` | Unbounded intermediate arrays in glob brace expansion (DoS) | `minimatch`/`glob`, used by Metro's file watcher, Jest, Babel |
| `uuid` (7.0.3) | Missing buffer bounds check in v3/v5/v6 when a `buf` arg is supplied | `expo` → `@expo/config-plugins` → `xcode` (iOS project-file generation during `expo prebuild`) — confirmed via `npm ls uuid`; unrelated to `expo-modules-core`'s own internal uuid helper, which isn't the flagged npm package |

Every one of these runs during `expo prebuild`, `metro bundle`/`expo
start`, or CI/EAS builds — processing the repo's own config files, glob
patterns, and asset files. None of them execute inside the shipped app
binary on a user's device, and none process attacker-controlled network
input at runtime. A remote attacker hitting CRAVE's API or app has no
path to any of these six packages. Real exploitability would require
control over the build machine's inputs (a malicious asset committed to
the repo, a compromised CI config) — a different threat model than "user
of the app."

**Conclusion: 0 of 26 findings are runtime-reachable by an external
attacker.** This matches the external audit's own caveat that the number
"must not be presented as 92 exploitable app vulnerabilities."

## Why `npm audit fix` doesn't help

`npm audit fix --dry-run --omit=dev` resolves nothing here: every fix's
version floor (checked per-package) falls inside the Expo 55–57 SDK
canary range, all of which sit above the currently pinned `expo ~54.0.33`
(installed: 54.0.36). There is no patch/minor version within SDK 54 that
carries any of these fixes — closing them for real means an Expo SDK
major upgrade (54 → 57), a real migration (native module compatibility,
dev client rebuild, full regression pass on every native feature: camera,
maps, notifications, uploads), not a dependency bump to do incidentally
alongside anything else. Scope that as its own deliberate project if/when
it's prioritized; don't `--force` it.

## Contrast: the backend finding from this same triage pass was real

Unlike the frontend's build-tooling-only findings, `pip-audit` on
`backend/requirements.txt` found `starlette==0.52.1` with 5 real CVEs
(PYSEC-2026-161/248/249/2280/2281) — and Starlette sits directly in every
request's path (used by FastAPI on every request). `requirements.txt` had
pinned `starlette>=0.40.0,<1.0.0`, a ceiling that was accurate when
written (starlette hadn't released 1.0 yet) but had gone stale — by now
starlette is at 1.6.x, and the old ceiling was silently blocking every
fix. Bumped the floor to `>=1.3.1` (verified against fastapi's own
`>=0.46.0` constraint — no upper bound), confirmed full backend suite
still passes at the installed 1.6.0, and `pip-audit` now reports zero
vulnerable packages. See `requirements.txt`'s own comment for the CVE-by-
CVE detail.

## Review

Re-run this triage (`npm audit --omit=dev`, `pip-audit -r
requirements.txt`) whenever a dependency PR touches `package-lock.json`
or `requirements.txt`, and revisit the Expo-54-is-still-current framing
whenever an SDK upgrade is actually scoped.
