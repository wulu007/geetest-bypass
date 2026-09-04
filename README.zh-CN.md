# wulu-geetest-bypass

<p align="center">
  <a href="https://github.com/wulu007/geetest-bypass/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/wulu007/geetest-bypass/ci.yml?label=CI&logo=github"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/wulu007/geetest-bypass/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/wulu007/geetest-bypass"><img src="https://img.shields.io/badge/geetest-v4-orange" alt="Geetest v4"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://static.pepy.tech/personalized-badge/wulu-geetest-bypass?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" alt="downloads"></a>
</p>

<p align="center">
 <a href="./README.md"><b>English</b></a> | <b>简体中文</b>
</p>

> 一个轻量级纯 Python 库，无需 Node.js 或无头浏览器即可自动通过 **极验行为验证 v4（Geetest Behavioral CAPTCHA v4）**。具备动态鼠标轨迹仿真、7 种内置风险类型求解器、无障碍语音绕过，以及可扩展的自定义求解器注册机制。

## ✨ Features

- 🚀 **纯 Python 3.11+** — 零 Node.js、零无头浏览器、零外部运行时依赖。
- 🛡️ **多风险类型支持** — 开箱即用的 7 种风险类型求解器（[完整表格见下](#supported-risk-types)）。
- 🎯 **拟人化轨迹仿真** — 每次运行都动态生成鼠标轨迹（非固定回放）。
- 🔁 **智能自动重试** — 单次调用 `resolve()` 在瞬时失败时自动重试最多 3 次。
- 🕹️ **精细的分步流程** — 分离的 `load()` 与 `verify()` 步骤，便于拦截 payload 与 token。
- ♿ **无障碍语音绕过** — 在语音通道开启时无缝切换至离线语音识别。
- 🔌 **可扩展求解器注册表** — 轻松接入自定义 OCR / 视觉模型，或覆盖内置求解器。
- 🌐 **高级网络能力** — 原生支持代理链、浏览器 TLS 指纹仿真与自定义请求头。

<a id="supported-risk-types"></a>
## 🧩 Supported Risk Types

| 类型 | 说明 | 依赖 | 支持 |
| ---- | ---- | ---- | ---- |
| `ai` | 静默验证 | 无 | ✅ |
| `slide` | 滑块拼图 | `[slide]` | ✅ |
| `match` | 3×3 连线 | 无 | ✅ |
| `winlinze` | 五子棋 | 无 | ✅ |
| `svg_seed` | SVG 3×3 图片选择 | `[svg]` | ✅ |
| `svg_icon` | SVG 2×2 图标选择 | `[svg]` | ✅ |
| `voice` | 语音验证 | `[voice]` | ✅ |
| `icon` | 图标点选 | 无 | ❌ |
| `word` | 文字点选 | 无 | ❌ |
| `nine` | 九宫格 | 无 | ❌ |
| `phrase` | 短语识别 | 无 | ❌ |
| `pencil` | 涂鸦 | 无 | ❌ |
| `space` | 空间推理 | 无 | ❌ |

`依赖` 列指向下方的[依赖组](#installation)。标记为 ❌ 的类型没有内置求解器，需通过[自定义求解器](#register-custom-solvers)自行注册。

<a id="installation"></a>
## 📦 Installation

推荐使用 `uv`（更快、更现代的 Python 包管理器）：

```bash
uv add "wulu-geetest-bypass[all]"
```

也可以直接使用 `pip`：

```bash
pip install "wulu-geetest-bypass[all]"
```

依赖组（按需安装）：

```bash
# voice 语音验证
uv add "wulu-geetest-bypass[voice]"

# slide 滑块拼图（需要 opencv）
uv add "wulu-geetest-bypass[slide]"

# SVG 动图选择
uv add "wulu-geetest-bypass[svg]"

# 安装全部
uv add "wulu-geetest-bypass[all]"
```

## 🚀 Quick Start

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

常见场景到这里就够了。重试控制、分步流程、语音模式、自定义求解器与 HTTP 配置见[进阶用法](#advanced-usage)。

<a id="advanced-usage"></a>
## 💡 Advanced Usage

### 自动重试与单次调用 `resolve()`

`resolve()` 把 `load()` 与 `verify()` 合为一次调用，失败时自动重试：

```python
g = Geetest(captcha_id='your_captcha_id', risk_type='slide')
result = await g.resolve()  # 默认：最多 3 次尝试
result = await g.resolve(retry=5)  # 覆盖尝试次数
```

最终失败时抛出 `VerifyError`，不会返回部分结果。

### 分步流程：`load()` → `verify()`

当需要在两个阶段之间介入（打日志、检查 payload、运行自己的识别逻辑）时，分开调用：

```python
g = Geetest(captcha_id='your_captcha_id', risk_type='slide')
data = (
    await g.load()
)  # 初始化数据：captcha_type, lot_number, payload, process_token, pow_detail, ...
response = await g.verify(data)  # 完整响应：status + data
```

`load()` 返回一个 dict，其字段可直接传给 `verify()`。返回类型见[数据模型](#data-models)。

### 无障碍（语音）模式

部分极验 v4 站点在服务端开启了语音通道（无障碍模式）。当站点支持时，**无论原始风险类型是什么**，都可以通过 `voice=True` 强制切换到语音验证，从而绕过原本的滑块 / 点选行为验证：

```python
# 原本是滑块验证，但该站点支持无障碍模式
g = Geetest(captcha_id='your_captcha_id', risk_type='slide', voice=True)
result = await g.resolve()
```

流程变为：加载语音验证码 → 下载音频 → 离线识别数字 → 提交验证。无需浏览器环境，也无需图像识别。

> **注意**：并非所有站点都开启无障碍通道。若不支持，`load()` 返回的 `show_voice` 字段为 `false`，此时设置 `voice=True` 不生效，仍使用原有的 `risk_type`。

<a id="register-custom-solvers"></a>
### 注册自定义求解器

对于没有内置支持的风险类型，可以通过 `register_solver` 注入自定义求解器：

```python
from wulu_geetest_bypass import Geetest


def solve_icon(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]: ...


Geetest.register_solver('icon', solve_icon)
```

注册后，`generate_w()` 会自动以对应的 payload 字段调用它。**点击/绘制类求解器返回相对验证图片的归一化坐标（取值 `[0, 1]`）**——库内部负责换算到窗口/协议格式（例如 `userresponse` 使用基于图片的百分比 × 10000），并生成点击轨迹（`icon` / `word` / `phrase` 会包含末尾的提交按钮点击）：

| 类型 | 求解器签名 |
| ---- | ---- |
| `icon` / `word` | `(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]` |
| `phrase` | `(imgs: bytes) -> list[tuple[float, float]]` |
| `nine` | `(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[tuple[int, int]]` |
| `pencil` | `(imgs: bytes) -> list` |
| `space` | 未单独内置；极验将 `space` 路由为 `svg_icon`（由 SVG 求解器处理） |

内置求解器也可以被覆盖，既可直接传入求解器，也可以用装饰器形式：

```python
Geetest.register_solver('slide', my_custom_slide_solver)
```

```python
@Geetest.register_solver('slide')
def my_custom_slide_solver(bg, slice, ypos): ...
```

### 代理与 HTTP 客户端配置

`Geetest` 把全部 HTTP 相关配置交给 `wreq`，因此代理、自定义请求头与客户端仿真只需在构造时配置一次。通过 `client_options` 传入 `ClientConfig`，或通过 `client` 传入已构造好的客户端（后者优先级更高）：

```python
from wreq import Client, ClientConfig

config = ClientConfig(...)  # 代理链、请求头、仿真、超时等

g = Geetest(captcha_id='your_captcha_id', risk_type='slide', client_options=config)
# 等价写法，需要自己先构造客户端时：
g = Geetest(captcha_id='your_captcha_id', risk_type='slide', client=Client(config))
```

## 📖 API Reference

### 配置项 — `Geetest(**options)`

| 参数 | 类型 | 说明 |
| ---- | ---- | ---- |
| `captcha_id` | `str` | 验证 ID（必填） |
| `risk_type` | `RiskType` | 风险类型，默认 `'ai'` |
| `client_type` | `ClientType` | 客户端类型，`'web'` / `'web_mobile'` / `'android'` / `'ios'` |
| `lang` | `Lang` | 语言，`'zho'` / `'eng'` / `'fra'` / `'deu'` 等共 17 种 |
| `challenge` | `str` | 自定义 challenge（省略时自动生成） |
| `user_info` | `Any` | 附加用户信息（预留） |
| `voice` | `bool` | 启用无障碍语音验证（需要 `[voice]`） |
| `client_options` | `wreq.ClientConfig` | HTTP 客户端配置（代理、请求头、仿真等） |
| `client` | `wreq.Client \| None` | 自定义 HTTP 客户端（优先于 `client_options`） |

<a id="data-models"></a>
### 数据模型

`load() -> dict` 返回初始化数据，包含 `captcha_type`、`lot_number`、`payload`、`process_token`、`pow_detail` 等字段，可直接传给 `verify()`。

`verify(data) -> VerifyResponse`：

```python
class VerifyResponse:
    status: str  # "success" / "fail" / "error"
    data: VerifyData  # 验证结果数据


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

`resolve(retry=3) -> Seccode`：

```python
class Seccode:
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str
```

| 参数 | 类型 | 说明 |
| ---- | ---- | ---- |
| `retry` | `int` | 失败重试次数，默认 `3` |

### 异常

| 异常 | 说明 |
| ---- | ---- |
| `GeetestError` | 所有自定义异常的基类 |
| `VerifyError` | 验证失败（重试次数已耗尽） |

## ⚖️ Disclaimer

本项目仅用于学习与研究目的。使用者应遵守相关法律法规与平台服务条款，严禁任何非法用途。作者不对因使用本项目而产生的任何法律问题承担责任。

## 🤝 Support & Updates

- 本项目持续跟踪极验 v4 行为验证的变更，并及时更新绕过逻辑与求解器。
- 遇到问题欢迎提交 [Issue](https://github.com/wulu007/geetest-bypass/issues)，也欢迎 PR。
- 如果本项目对你有帮助，欢迎点个 ⭐ Star 支持持续开发。

## 📄 License

本项目基于 MIT License 发布，详见 [LICENSE](./LICENSE)。
