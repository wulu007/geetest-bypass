# wulu-geetest-bypass

<p>
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/geetest-v4-orange" alt="Geetest v4">
  <img src="https://img.shields.io/badge/risk_types-5-brightgreen" alt="5 risk types">
</p>

Geetest CAPTCHA v4 自动化验证库，支持 `ai` / `slide` / `match` / `winlinze` / `svg_seed` 五种风险类型。

## 安装

```bash
uv add "wulu-geetest-bypass[all]"
```

可选依赖：

```bash
# slide 滑块（需要 opencv）
uv add "wulu-geetest-bypass[slide]"

# svg-seed 图片选择 + slide
uv add "wulu-geetest-bypass[svg-seed]"

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

## 风险类型

| 类型 | 说明 | 依赖 |
|------|------|------|
| `ai` | 无感验证 | 无 |
| `slide` | 滑块拼图 | opencv-python |
| `match` | 3×3 连线 | 无 |
| `winlinze` | 五子棋 | 无 |
| `svg_seed` | SVG 图片选择 | pillow, resvg-py, opencv-python |

## API

### `Geetest(captcha_id, risk_type, ...)`

| 参数 | 说明 |
|------|------|
| `captcha_id` | 验证 ID |
| `risk_type` | 风险类型，默认 `ai` |
| `client_type` | 客户端类型 `web` / `android` / `ios` |
| `lang` | 语言 `zh` / `en` |
| `challenge` | 自定义 challenge（默认随机 UUID） |
| `proxy` | 代理 URL |
| `client` | 自定义 `wreq.Client` 实例 |

### 方法

| 方法 | 说明 |
|------|------|
| `load()` | 获取验证数据 |
| `verify(data)` | 提交验证 |
| `resolve()` | load + verify，返回 `seccode` |

## 免责声明

本项目仅供学习和研究使用。使用者应遵守相关法律法规及平台服务条款，
禁止用于任何非法用途。作者不对因使用本项目产生的任何法律问题承担责任。