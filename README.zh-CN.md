# wulu-geetest-bypass

<p align="center">
  <a href="https://github.com/wulu007/geetest-bypass/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/wulu007/geetest-bypass/ci.yml?label=CI&logo=github"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/wulu007/geetest-bypass/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/wulu007/geetest-bypass"><img src="https://img.shields.io/badge/geetest-v4-orange" alt="Geetest v4"></a>
  <a href="https://pypi.org/project/wulu-geetest-bypass/"><img src="https://static.pepy.tech/personalized-badge/wulu-geetest-bypass?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" alt="downloads"></a>
</p>

<p align="center">
| <a href="./README.md"><b>English</b></a> | <b>简体中文</b> |
</p>

纯 Python 实现的极验行为验证 v4 自动化通过库（无需 Node.js）。自动处理 `ai` / `slide` / `match` / `winlinze` / `svg_seed` / `svg_icon` / `voice` 七种风险类型，支持自定义重试、代理和 HTTP 客户端。

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
# voice 语音验证
uv add "wulu-geetest-bypass[voice]"

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

| 类型       | 说明             | 依赖      | 支持 |
| ---------- | ---------------- | --------- | ---- |
| `ai`       | 无感验证         | 无        | ✅    |
| `slide`    | 滑块拼图         | `[slide]` | ✅    |
| `match`    | 3×3 连线         | 无        | ✅    |
| `winlinze` | 五子棋           | 无        | ✅    |
| `svg_seed` | SVG 3x3 图片选择 | `[svg]`   | ✅    |
| `svg_icon` | SVG 2x2 图标选择 | `[svg]`   | ✅    |
| `voice`    | 语音验证         | `[voice]` | ✅    |
| `icon`     | 图标点选         | 无        | ❌    |
| `word`     | 文字点选         | 无        | ❌    |
| `nine`     | 九宫格           | 无        | ❌    |
| `phrase`   | 短语识别         | 无        | ❌    |
| `pencil`   | 涂鸦             | 无        | ❌    |
| `space`    | 空间推理         | 无        | ❓    |

## API

### `Geetest(**options)`

| 参数             | 类型                  | 说明                                                         |
| ---------------- | --------------------- | ------------------------------------------------------------ |
| `captcha_id`     | `str`                 | 验证 ID（必填）                                              |
| `risk_type`      | `RiskType`            | 风险类型，默认 `'ai'`                                        |
| `client_type`    | `ClientType`          | 客户端类型，`'web'` / `'web_mobile'` / `'android'` / `'ios'` |
| `lang`           | `Lang`                | 语言，`'zho'` / `'eng'` / `'fra'` / `'deu'` 等 13 种           |
| `challenge`      | `str`                 | 自定义 challenge（不传则自动生成）                           |
| `user_info`      | `Any`                 | 附加用户信息（预留）                                         |
| `voice`          | `bool`                | 启用无障碍语音验证（需要 `[voice]` 依赖）                    |
| `client_options` | `wreq.ClientConfig`   | HTTP 客户端配置（代理、headers、模拟等）                     |
| `client`         | `wreq.Client \| None` | 自定义 HTTP 客户端（优先级高于 `client_options`）            |

### 方法

#### `load() -> dict`

获取验证初始化数据，返回值包含 `captcha_type`、`lot_number`、`payload`、`process_token`、`pow_detail` 等字段，可直接传入 `verify()`。

#### `verify(data) -> VerifyResponse`

提交验证并返回完整响应：

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

| 参数    | 类型  | 说明                   |
| ------- | ----- | ---------------------- |
| `retry` | `int` | 失败重试次数，默认 `3` |

### 注册自定义 Solver

对于未内置支持的风险类型，可通过 `register_solver` 注入自定义求解器：

```python
from wulu_geetest_bypass import Geetest


def solve_icon(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]: ...


Geetest.register_solver('icon', solve_icon)
```

注册后 `generate_w()` 会自动调用，传入对应的 payload 字段。**点击/绘制类 solver 返回相对验证图片的归一化坐标（取值 `[0, 1]`）**，库内部负责换算到窗口/协议格式（如 `userresponse` 使用基于图片的百分比×10000），并为 `icon` / `word` / `phrase` 自动生成点击轨迹（含末尾提交按钮点击）：

| 类型 | Solver 签名 |
|------|------------|
| `icon` / `word` | `(imgs: bytes, ques: list[bytes]) -> list[tuple[float, float]]` |
| `phrase` | `(imgs: bytes) -> list[tuple[float, float]]` |
| `nine` | `(imgs: bytes, ques: list[bytes], nine_nums: int) -> list[tuple[int, int]]` |
| `pencil` | `(imgs: bytes) -> list` |
| `space` | 同 SVG，由内置 solver 兜底 |

内置 solver 也可被覆盖：

```python
Geetest.register_solver('slide', my_custom_slide_solver)
```


### 无障碍模式

极验 v4 的部分站点在服务端开启了语音验证通道（无障碍模式）。当站点支持时，**无论原始风险类型是什么**，都可以通过 `voice=True` 强制切换到语音验证，从而绕过原本的滑块、点选等行为验证。

```python
# 原本是滑块验证，但站点支持无障碍模式
g = Geetest(captcha_id='your_captcha_id', risk_type='slide', voice=True)
result = await g.resolve()
```

切换后流程变为：加载语音验证码 → 下载音频 → 离线识别数字 → 提交验证。全程无需浏览器环境，不需处理图片识别。

> **注意**：并非所有站点都开启了无障碍通道。如果站点不支持，`load()` 返回的 `show_voice` 字段为 `false`，此时设置 `voice=True` 不会生效，仍按原 `risk_type` 处理。

### 异常

| 异常           | 说明                         |
| -------------- | ---------------------------- |
| `GeetestError` | 所有自定义异常的基类         |
| `VerifyError`  | 验证失败（所有重试均未通过） |

## 支持与更新

- 本项目会持续跟踪极验 v4 的行为验证变化，及时更新绕过逻辑与 solver。
- 遇到问题欢迎提交 [Issue](https://github.com/wulu007/geetest-bypass/issues)，也欢迎通过 PR 贡献代码。
- 如果本项目对你有所帮助，欢迎点个 ⭐ Star 鼓励作者持续更新。

## 免责声明

本项目仅供学习和研究使用。使用者应遵守相关法律法规及平台服务条款，
禁止用于任何非法用途。作者不对因使用本项目产生的任何法律问题承担责任。
