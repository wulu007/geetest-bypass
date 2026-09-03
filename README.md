# wulu-geetest-bypass

<p align="center">
  <a href="https://github.com/wulu007/geetest-bypass/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/wulu007/geetest-bypass/ci.yml?label=CI&logo=github"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/wulu007/geetest-bypass/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/wulu007/geetest-bypass"><img src="https://img.shields.io/badge/geetest-v4-orange" alt="Geetest v4"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://static.pepy.tech/personalized-badge/wulu-geetest-bypass?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" alt="downloads"></a>
</p>

<p align="center">
| <b>English</b> | <a href="./README.zh-CN.md"><b>简体中文</b></a> |
</p>

A pure Python library to pass Geetest behavioral CAPTCHA v4 automatically (no Node.js required). Handles seven risk types: `ai` / `slide` / `match` / `winlinze` / `svg_seed` / `svg_icon` / `voice`, with support for custom retry, proxies, and HTTP clients.

## Installation

`uv` is recommended (faster, more modern Python package manager):

```bash
uv add "wulu-geetest-bypass[all]"
```

You can also use `pip`:

```bash
pip install "wulu-geetest-bypass[all]"
```

Optional dependencies:

```bash
# voice verification
uv add "wulu-geetest-bypass[voice]"

# slide puzzle (requires opencv)
uv add "wulu-geetest-bypass[slide]"

# svg SVG icon selection + slide
uv add "wulu-geetest-bypass[svg]"

# everything
uv add "wulu-geetest-bypass[all]"
```

## Quick Start

```python
import asyncio
from wulu_geetest_bypass import Geetest


async def main():
    g = Geetest(captcha_id='your_captcha_id', risk_type='slide')
    result = await g.resolve()
    print(result)
    # {
    #     "captcha_id": "xxx",
    #     "lot_number": "xxx",
    #     "pass_token": "xxx",
    #     "gen_time": "xxx",
    #     "captcha_output": "xxx"
    # }


asyncio.run(main())
```

Each verification retries up to 3 times automatically (adjustable via the `retry` parameter), and raises `VerifyError` on failure.

## Risk Types

| Type       | Description              | Dependency | Support |
| ---------- | ------------------------ | ---------- | ------- |
| `ai`       | Silent verification      | none       | ✅      |
| `slide`    | Slider puzzle            | `[slide]`  | ✅      |
| `match`    | 3×3 connect              | none       | ✅      |
| `winlinze` | Gomoku                   | none       | ✅      |
| `svg_seed` | SVG 3x3 image selection  | `[svg]`    | ✅      |
| `svg_icon` | SVG 2x2 icon selection   | `[svg]`    | ✅      |
| `voice`    | Voice verification       | `[voice]`  | ✅      |
| `icon`     | Icon click               | none       | ❌      |
| `word`     | Word click               | none       | ❌      |
| `nine`     | Nine-grid                | none       | ❌      |
| `phrase`   | Phrase recognition       | none       | ❌      |
| `pencil`   | Doodle                   | none       | ❌      |
| `space`    | Spatial reasoning        | none       | ❓      |

## API

### `Geetest(**options)`

| Parameter         | Type                  | Description                                                  |
| ----------------- | --------------------- | ------------------------------------------------------------ |
| `captcha_id`      | `str`                 | Verification ID (required)                                   |
| `risk_type`       | `RiskType`            | Risk type, default `'ai'`                                    |
| `client_type`     | `ClientType`          | Client type, `'web'` / `'web_mobile'` / `'android'` / `'ios'` |
| `lang`            | `Lang`                | Language, `'zho'` / `'eng'` / `'fra'` / `'deu'` and 13 more  |
| `challenge`       | `str`                 | Custom challenge (auto-generated if omitted)                 |
| `user_info`       | `Any`                 | Extra user info (reserved)                                   |
| `voice`           | `bool`                | Enable accessible voice verification (requires `[voice]`)    |
| `client_options`  | `wreq.ClientConfig`   | HTTP client config (proxy, headers, emulation, etc.)         |
| `client`          | `wreq.Client \| None` | Custom HTTP client (takes priority over `client_options`)    |

### Methods

#### `load() -> dict`

Fetches verification init data. The return value includes `captcha_type`, `lot_number`, `payload`, `process_token`, `pow_detail` and other fields, which can be passed directly to `verify()`.

#### `verify(data) -> VerifyResponse`

Submits the verification and returns the full response:

```python
class VerifyResponse:
    status: str  # "success" / "fail" / "error"
    data: VerifyData  # verification result data


class VerifyData:
    lot_number: str
    result: str  # "success" / "fail"
    fail_count: int
    seccode: Seccode
    score: str
    payload: str
    process_token: str
    payload_protocol: int
```

#### `resolve(retry=3) -> Seccode`

One-call `load()` + `verify()`, retries automatically on failure, returns `Seccode`:

```python
class Seccode:
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str
```

| Parameter | Type  | Description                          |
| --------- | ----- | ------------------------------------ |
| `retry`   | `int` | Retry count on failure, default `3`  |

### Registering Custom Solvers

For risk types without built-in support, inject a custom solver via `register_solver`:

```python
from wulu_geetest_bypass import Geetest


def solve_icon(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]: ...


Geetest.register_solver('icon', solve_icon)
```

Once registered, `generate_w()` calls it automatically with the corresponding payload fields. **Click/draw solvers return normalized coordinates in `[0, 1]` relative to the verification image** — the library takes care of scaling them to the window/payload formats (e.g. `userresponse` uses image-based percent × 10000) and of generating the click tracks (including the final submit-button click for `icon`/`word`/`phrase`):

| Type                          | Solver signature                                              |
| ----------------------------- | ------------------------------------------------------------- |
| `icon` / `word`               | `(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]` |
| `phrase`                      | `(imgs: bytes) -> list[tuple[float, float]]`                  |
| `nine`                        | `(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[tuple[int, int]]` |
| `pencil`                      | `(imgs: bytes) -> list`                                       |
| `space`                       | Same as SVG, handled by built-in solver as fallback           |

Built-in solvers can also be overridden:

```python
Geetest.register_solver('slide', my_custom_slide_solver)
```

```python
Geetest.register_solver('slide', my_custom_slide_solver)
```

### Accessible Mode

Some Geetest v4 sites enable the voice channel (accessible mode) server-side. When a site supports it, **regardless of the original risk type**, you can force voice verification via `voice=True`, bypassing the original slider / click behavioral checks.

```python
# Originally a slide verification, but the site supports accessible mode
g = Geetest(captcha_id='your_captcha_id', risk_type='slide', voice=True)
result = await g.resolve()
```

The flow becomes: load voice captcha → download audio → recognize digits offline → submit verification. No browser environment or image recognition needed.

> **Note**: Not all sites enable the accessible channel. If unsupported, the `show_voice` field in `load()` returns `false`, and setting `voice=True` has no effect — the original `risk_type` is still used.

### Exceptions

| Exception        | Description                                            |
| ---------------- | ------------------------------------------------------ |
| `GeetestError`   | Base class of all custom exceptions                    |
| `VerifyError`    | Verification failed (all retries exhausted)            |

## Support & Updates

- This project continuously tracks Geetest v4 behavioral verification changes and updates the bypass logic and solvers promptly.
- Please open an [Issue](https://github.com/wulu007/geetest-bypass/issues) if you encounter problems, and PRs are welcome.
- If this project helps you, feel free to give it a ⭐ Star to encourage continued development.

## Disclaimer

This project is for learning and research purposes only. Users should comply with applicable laws and platform terms of service; any illegal use is prohibited. The author assumes no responsibility for any legal issues arising from the use of this project.
