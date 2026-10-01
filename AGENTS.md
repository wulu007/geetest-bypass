# wulu-geetest-bypass

Geetest CAPTCHA v4 bypass library. Pure Python 3.11+ at runtime — no Node.js, no browser.

## Commands

```bash
# install: dev group + every workspace member (extensions/*)
uv sync

# run all tests
uv run pytest tests/

# focused test
uv run pytest tests/ -k test_svg_seed -v

# extension tests
uv run pytest extensions/wulu-geetest-bypass-voice/tests/

# lint, then format — order matters, --fix rewrites imports
uv run ruff check --fix
uv run ruff format

# type check (local only, not in CI)
uv run pyrefly check

# build
uv build
uv build extensions/wulu-geetest-bypass-voice

# publish (requires a PyPI token)
uv publish
```

- Ruff: `select = [E, F, I, B, UP, SIM, C4]`, `ignore = [E501, B008, RUF001, RUF002]`, single quotes.
- pytest: `addopts = "-s"` (stdout not captured).
- pyrefly suppressions are inline: `# pyrefly: ignore [code]`.
- Git hooks are `prek` (`prek.toml`): trailing-whitespace, end-of-file-fixer, check-added-large-files, `ruff-check --fix`, `ruff-format`.
- CI (`ci.yml`) runs **only** `uvx ruff check` + `uvx ruff format --check` on Python 3.11 — no tests. Publishing runs on `v[0-9]*` tags; `publish-voice.yml` publishes the extension on `voice-v*` tags.

## Architecture

- **`Geetest`** (`geetest.py:55`): the whole client. `load()` → `auto_solve()` → `generate_w()` → `verify()`; `resolve(retry=3)` wraps that loop. `_solvers` maps `captcha_type` → solver, `register_solver()` overrides entries.
- **`_type.py`**: every TypedDict and Literal — `RiskType` / `ClientType` / `Lang`, one payload shape per captcha type unioned into `WPayload`, `Seccode`, `VerifyData` / `VerifyResponse`, `Encryption`, `GeetestOptions`, and the solver `Callable` aliases.
- **`parser/`**: `generate_pow()` (proof-of-work) and `parse_abo_pair()` (the per-build `abo` key/value pair). Pure stdlib.
- **`crypto.py`**: `build_w()` encrypts the payload — `pt=0` base64url, `pt=1` AES-128-CBC + RSA-1024, `pt=2` SM4-CBC + SM2. `gen_td_sign()` is HMAC-SHA256 over the track.
- **`config.py`**: `Config.from_static_path()` turns the `/load` `static_path` into a `Patrol` (`biht`, `lib_key`/`lib_val`, `abo_key`/`abo_val`, `track_enable`) read from `data/<major>-config.json`. There is deliberately no fallback — an unrecorded build raises `ConfigError`. `register_patrol()` adds or overrides an entry. `Config.em` and `Config.gee_guard` are constants and are not in the JSON.
- **`solver/`**: lazy-loaded through module `__getattr__` — a missing optional dep returns a stub raising `ImportError` that names the extra to install. `match.py` and `winlinze.py` are pure Python; `slide.py` needs the `slide` extra (opencv); `svg.py` needs the `svg` extra (resvg-py + pillow + opencv) and also exports `frame_times()`. Third-party solvers register under the `wulu_geetest_bypass.solvers` entry point group (entry point name = `captcha_type`); `discover_plugins()` collects them into `Geetest._solvers` at import time.
- **`track/`**: `TrackBuilder` (bezier + jitter) plus the `gen_*_track()` generators in `generators.py`; `track_zip()` / `track_unzip()` implement the SDK's track codec; `types.py` holds `TrackType` / `PointerType` / `TrackPayload`.
- **`_exceptions.py`**: `GeetestError` (base), `ConfigError`, `RateLimitError`, `VerifyError`. None of them are re-exported from `__init__.py`.
- **`extensions/*`** are uv workspace members. `wulu-geetest-bypass-voice` is the offline MFCC digit recogniser (`solve_voice`): it ships `{lang}.npz` templates for 12 languages and registers the `voice` entry point. Regenerate templates with `scripts/build_voice_templates.py`.

## Key gotchas

- Use `uv`, not `pip`. Interpreter is 3.11 (`.python-version`); the venv is `.venv`.
- The extras (`voice`, `slide`, `svg`, `image`, `all`) are for downstream installs. In this repo `uv sync` already brings in every workspace member and dev dependency.
- `tests/test_geetest.py` and `tests/test_svg.py` call the live Geetest API (`conftest.py` holds the `captcha_id`) and dump images into `resources/` (gitignored). They need network, and results depend on the exit IP.
- `scripts/extract-config.mjs` is the only Node.js piece. CI runs it daily; locally it accepts `--dry-run` or a local SDK file (which implies `--dry-run`).
- `Geetest.default_headers` deliberately omits `Referer`: a real browser on a `file://` page sends none, and sending the geetest one flips some sites to `fail`.
- Client emulation defaults to `Emulation.Chrome147`. Switching it to `Edge147` gets `forbidden` from at least one production site.
- `GeetestOptions` declares `challenge` and `user_info`, but `Geetest.__init__` ignores both.
- `client_options` is annotated `ClientConfig`, but `wreq` exports no such name — it is a plain kwargs dict splatted into `Client(**client_options)`.
- `TrackBuilder._compress` mirrors the SDK's track downsampler (`gg4.js` `$_BHGR`): head + newest moves + every action. It deliberately does **not** re-sort by timestamp.
- `.shatter/` (gitignored) holds the deobfuscated `gg4.js` / `gcaptcha4_deob.js` — the reference for track, crypto and config behaviour.
- Untracked local scratch can break repo-wide `ruff` / `pytest` runs; scope the command or check `git status` first.
- Never commit without an explicit request. Conventional commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`, `revert:`.
- Daily `update-config.yml` (23:00 UTC) re-extracts `data/*.json` from live sites, bumps the patch version, commits straight to `main` and pushes the tag.
