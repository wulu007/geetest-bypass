# Geetest v4 前端 SDK 变更日志

> 记录极验 v4 前端 SDK（`gcaptcha4.js` / `gt4.js`）各版本在 `w` 载荷、环境检测、题型与配置机制上的变更。

## v1.9.10

### 1. `w` 载荷新增 `ce` 与 `cd`

提交 `/verify` 前，`w` 明文载荷新增两个环境检测字段：

#### `ce` — 云环境 / 运行时特征快照

由 `getCloudEnvironmentSnapshot()` 惰性采集并缓存在实例上，`destroy()` 时清空。总采样预算为 **20 ms**，超时后未执行项的状态码记为 `BUDGET`（`2`）。

数据结构示例：

```json
{
  "v": 1,
  "g1": 16,
  "g2": 8,
  "g3": [1920, 1080],
  "g8": "Win32",
  "g17": { "v5": "ANGLE (NVIDIA, ...)" },
  "s": { "g1": 0, "g2": 0, "g3": 0, "g8": 0, "g17": 0 }
}
```

| 字段 | 采集内容 | 说明与特殊分支 |
| :--- | :--- | :--- |
| `v` | 固定版本号 | 恒为 `1` |
| `g1` | `navigator.hardwareConcurrency` | 须为正整数，否则状态记为 `INVALID` |
| `g2` | `navigator.deviceMemory` | 须为正数，否则状态记为 `INVALID` |
| `g3` | `[screen.width, screen.height]` | 降序排列；检测到 Safari 特征分支时直接返回 `UNSUPPORTED` |
| `g8` | `navigator.platform` | `MacIntel` 下结合 Safari / 触控特征规范化为 `iPad` / `iPhone` |
| `g17` | `{"v5": "<UNMASKED_RENDERER_WEBGL>"}` | 通过 `WEBGL_debug_renderer_info` 读取，并在 `finally` 中调用 `WEBGL_lose_context` 释放上下文；Firefox 特征分支直接返回 `UNSUPPORTED` |
| `s` | 各字段状态码对象 | `OK=0`、`UNSUPPORTED=1`、`BUDGET=2`、`BLOCKED=3`、`ERROR=4`、`INVALID=5` |

#### `cd` — DevTools / CDP 探针

在最多 3 个隐藏 `iframe` 中依次运行以下探针（单探针观察窗口 **150 ms**，总 deadline **220 ms**）：

| 索引 | 探针 | 检测机制 |
| :---: | :--- | :--- |
| `0` | `nativeStack` | 为 `Error.stack` 定义 getter 后调用 `console.debug(err)`，检测控制台是否读取堆栈 |
| `1` | `eagerStack` | 临时覆写 `Error.prepareStackTrace`，调用 `console.groupEnd(err)` 后比对 `err.stack` |
| `2` | `bindingShape` | 检查 `iframe` 内原生函数（`name`、`prototype`、`Function.prototype.toString`）形态 |

- 状态码：`MISS=0`、`HIT=1`、`UNSUPPORTED=2`、`TIMEOUT=3`、`BLOCKED=4`、`ERROR=5`。
- 正常未打开 DevTools 的真实浏览器返回 `[0, 0, 0]`；探针无法运行或异常时回退为 `[5, 5, 5]`。

### 2. 新增 `canvas` 题型

UI 工厂新增 `canvas` 题型分支：

- 协议版本：`sceneProtocol` 必须为 `1`（否则抛出 `Unsupported canvas protocol`）。
- `answerPath`：v2 prompt 对象，`content` 数组最多 32 项（支持 `text` / `image` / `break` 节点，最多 8 张 base64 图片，总字符预算 20000，像素预算 4 MiB）。
- `questionPath`：经 `pako` 解压的 v2 二进制场景包（`renderer: "canvas2d"`、`encoding: "varint-paths+delta-keyframes"`），使用 `background` / `foreground` 双 `<canvas>` 渲染并支持键盘交互。

## v1.9.9

- **`w` 载荷新增 `nd`、`tc`、`tz`**：
  - `nd`：`NodeEnvHoneypot` 7 槽位检测向量，真实浏览器全为 `0`（`[0, 0, 0, 0, 0, 0, 0]`）。
  - `tc`：触控能力检测（`{"mtp": 0, "te": false, "ts": false}`）。其中 `te` 通过 `Document.createEvent("TouchEvent")` 检测，Chrome 会直接抛出 `NotSupportedError`，实际恒为 `false`。
  - `tz`：时区信息（`{"zone": "<IANA>", "offset": <minutes>}`）。

## v1.9.8

- 新增环境蜜罐逻辑：检测到 Node 或 DOM shim 运行环境时，会重写 `lib._abo` 为标记值。

## v1.9.7

- 新增轨迹上报字段（`td` 与 `td_sign`）。
