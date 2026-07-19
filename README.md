# wulu-geetest-bypass

<p>
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/geetest-v4-orange" alt="Geetest v4">
  <img src="https://img.shields.io/badge/risk_types-13-lightgrey" alt="13 risk types">
</p>

纯 Python 实现的极验行为验证 v4 自动化通过库（无需 Node.js）。自动处理 `ai` / `slide` / `match` / `winlinze` / `svg_seed` / `svg_icon` 六种风险类型，支持自定义重试、代理和 HTTP 客户端。

## 安装

推荐使用 `uv`（更快、更现代的 Python 包管理器）：

```bash
uv add "wulu-geetest-bypass[all]"
```

也可用 `pip`：

```bash
pip install "wulu-geetest-bypass[all]"
```

可选依赖：

```bash
# slide 滑块（需要 opencv）
uv add "wulu-geetest-bypass[slide]"

# svg SVG 图标选择 + slide
uv add "wulu-geetest-bypass[svg]"

# 全部安装
uv add "wulu-geetest-bypass[all]"
```

## 快速开始

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

每次验证会自动重试最多 3 次（可通过 `retry` 参数调整），失败时抛出 `VerifyError`。

## 风险类型

| 类型 | 说明 | 依赖 | 支持 |
|------|------|------|------|
| `ai` | 无感验证 | 无 | ✅ |
| `slide` | 滑块拼图 | `[slide]` | ✅ |
| `match` | 3×3 连线 & 9宫格 | 无 | ✅ |
| `winlinze` | 五子棋 | 无 | ✅ |
| `svg_seed` | SVG 图片选择 | `[svg]` | ✅ |
| `svg_icon` | SVG 图标选择 | `[svg]` | ✅ |
| `voice` | 语音验证 | `[voice]` | ✅ |
| `icon` | 图标点选 | 无 | ❌ |
| `word` | 文字点选 | 无 | ❌ |
| `nine` | 九宫格 | 无 | ❌ |
| `phrase` | 短语识别 | 无 | ❓ |
| `space` | 空间推理 | 无 | ❓ |
| `pencil` | 涂鸦 | 无 | ❓ |

## API

### `Geetest(**options)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `captcha_id` | `str` | 验证 ID（必填）|
| `risk_type` | `RiskType` | 风险类型，默认 `'ai'` |
| `client_type` | `ClientType` | 客户端类型，`'web'` / `'web_mobile'` / `'android'` / `'ios'` |
| `lang` | `Lang` | 语言，`'zh'` / `'en'` / `'zho'` / `'eng'` |
| `challenge` | `str` | 自定义 challenge（不传则自动生成）|
| `user_info` | `Any` | 附加用户信息（预留）|
| `client_options` | `wreq.ClientConfig` | HTTP 客户端配置（代理、headers、模拟等）|
| `client` | `wreq.Client \| None` | 自定义 HTTP 客户端（优先级高于 `client_options`）|

### 方法

#### `load() -> dict`

获取验证初始化数据，返回值包含 `captcha_type`、`lot_number`、`payload`、`process_token`、`pow_detail` 等字段，可直接传入 `verify()`。

#### `verify(data) -> VerifyResponse`

提交验证并返回完整响应：

```python
class VerifyResponse:
    status: str                          # "success" / "fail" / "error"
    data: VerifyData                     # 验证结果数据

class VerifyData:
    lot_number: str
    result: str                          # "success" / "fail"
    fail_count: int
    seccode: Seccode
    score: str
    payload: str
    process_token: str
    payload_protocol: int
```

#### `resolve(retry=3) -> Seccode`

一键完成 `load()` + `verify()`，验证失败时自动重试，返回 `Seccode`：

```python
class Seccode:
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `retry` | `int` | 失败重试次数，默认 `3` |

### 异常

| 异常 | 说明 |
|------|------|
| `GeetestError` | 所有自定义异常的基类 |
| `VerifyError` | 验证失败（所有重试均未通过）|

## 免责声明

本项目仅供学习和研究使用。使用者应遵守相关法律法规及平台服务条款，
禁止用于任何非法用途。作者不对因使用本项目产生的任何法律问题承担责任。