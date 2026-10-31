# Geetest v4 Benchmark: Pass Rate and Latency

English | [简体中文](BENCHMARK.zh-CN.md)

> Measured against the live service with fully automated, continuous sampling. Shows the pass rate and latency of every captcha type in `wulu-geetest-bypass`.
> Each type is tested in separate batches, so see the test time column in the overview. `–` means not measured or too few samples.

---

## 1. Overview

| Type | Tested at | Live samples | First-try pass rate | 95% CI | With 1 retry (est.) | Solver P50 | E2E P50 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **slide** | 2026-10-31 | 50 | **98.0%** | 89.5% ~ 99.6% | 100.0% | 2.0 ms | 273.6 ms |
| **voice** | 2026-10-31 | 50 | **100.0%** | 92.9% ~ 100.0% | 100.0% | 16.1 ms | 259.0 ms |
| **icon** | 2026-10-31 | 50 | **96.0%** | 86.5% ~ 98.9% | 99.8% | 27.7 ms | 309.2 ms |
| **phrase** | 2026-10-31 | 50 | **94.0%** | 83.8% ~ 97.9% | 99.6% | 40.5 ms | 260.0 ms |
| **nine** | 2026-10-31 | 50 | **100.0%** | 92.9% ~ 100.0% | 100.0% | 21.0 ms | 244.0 ms |
| **word** | 2026-10-31 | 50 | **100.0%** | 92.9% ~ 100.0% | 100.0% | 29.8 ms | 286.5 ms |
| **svg_seed** | 2026-10-31 | 50 | **100.0%** | 92.9% ~ 100.0% | 100.0% | 26.2 ms | 249.4 ms |
| **svg_icon** | 2026-10-31 | 50 | **96.0%** | 86.5% ~ 98.9% | 99.8% | 21.0 ms | 283.3 ms |

> **Notes**:
> - **First-try pass rate**: probability that a single submission succeeds with no retry, `passed / submitted`. The **95% CI** is the Wilson interval; the fewer the samples, the wider it is. Compare types by the interval, not the point value.
> - **With 1 retry (est.)**: estimated as `1 − (1 − p)²`, not measured.
> - **Solver P50**: local CPU time for image preprocessing, model inference and coordinate assignment, from live samples only (the same batch as the pass rate). Offline benchmark data is in section 2.2 and is not part of the overview.
> - **E2E P50**: the full `load` → `verify` cycle including network. It varies with exit IP and network conditions.

---

## 2. Solver Latency

### 2.1 Live samples

Unit: ms. Each real challenge is timed once, so first-call cold-start effects are included. These are the same challenges as the pass rate in section 1.

| Type | Samples (challenges) | Min | P50 | P90 | P95 | P99 | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **slide** | 50 | 1.4 | 2.0 | 2.9 | 3.0 | – | 3.4 |
| **voice** | 50 | 13.6 | 16.1 | 17.3 | 17.7 | – | 18.1 |
| **icon** | 48 | 22.8 | 27.7 | 29.1 | 29.4 | – | 30.4 |
| **phrase** | 50 | 33.8 | 40.5 | 44.9 | 46.1 | – | 51.1 |
| **nine** | 50 | 15.2 | 21.0 | 26.5 | 26.8 | – | 27.1 |
| **word** | 50 | 23.3 | 29.8 | 33.7 | 35.5 | – | 37.5 |
| **svg_seed** | 50 | 22.9 | 26.2 | 29.7 | 31.5 | – | 50.8 |
| **svg_icon** | 50 | 19.4 | 21.0 | 22.0 | 22.2 | – | 23.1 |

> P99 is hidden (`–`) when there are fewer than 100 samples.

### 2.2 Offline benchmark (regression reference)

Unit: ms. One fixed sample repeated over many rounds with pytest-benchmark; warm data, no cold start. Rounds are not independent samples, and these numbers must not be compared with 2.1. Use them to check whether a change made things slower on the same machine.

| Type | Tested at | Rounds | Min | P50 | P90 | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **slide** | 2026-10-31 | 189 | 1.6 | 1.7 | 1.8 | 2.0 |
| **voice** | 2026-10-31 | 32 | 20.0 | 21.9 | 23.3 | 24.3 |
| **icon** | 2026-10-31 | 25 | 26.2 | 29.6 | 31.2 | 31.4 |
| **phrase** | 2026-10-31 | 25 | 35.3 | 38.4 | 42.9 | 45.3 |
| **nine** | 2026-10-31 | 48 | 14.8 | 18.9 | 20.6 | 21.7 |
| **word** | 2026-10-31 | 25 | 26.9 | 31.5 | 35.8 | 44.7 |
| **svg_seed** | 2026-10-31 | 25 | 24.4 | 25.4 | 26.3 | 27.8 |
| **svg_icon** | 2026-10-31 | 25 | 20.3 | 21.6 | 24.7 | 30.2 |


---

## 3. End-to-End Latency

Unit: ms, including network round trips. Only challenges that were actually submitted are counted (rate-limited or blocked ones are excluded).

| Type | Samples | Min | P50 | P90 | P95 | P99 | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **slide** | 50 | 244.4 | 273.6 | 305.3 | 326.0 | – | 455.6 |
| **voice** | 50 | 229.7 | 259.0 | 307.8 | 348.0 | – | 416.6 |
| **icon** | 48 | 255.5 | 309.2 | 415.2 | 510.8 | – | 917.9 |
| **phrase** | 50 | 236.3 | 260.0 | 368.9 | 416.4 | – | 1029.0 |
| **nine** | 50 | 211.4 | 244.0 | 304.8 | 327.3 | – | 467.5 |
| **word** | 50 | 244.6 | 286.5 | 358.2 | 400.7 | – | 635.6 |
| **svg_seed** | 50 | 216.8 | 249.4 | 287.2 | 304.0 | – | 398.8 |
| **svg_icon** | 50 | 231.3 | 283.3 | 475.5 | 586.6 | – | 765.0 |

---

## 4. Test Environment

All local inference was measured on CPU only:

| Item | Value |
| :--- | :--- |
| **CPU** | AMD Ryzen 7 8845HS w/ Radeon 780M Graphics (16 cores) |
| **OS** | Windows 10 |
| **Python** | Python 3.11.13 |
| **Inference backend** | ONNX Runtime (`CPUExecutionProvider`) / OpenCV |
| **Environment recorded at** | 2026-10-31 (the latest test session's environment, not each type's sampling time) |
