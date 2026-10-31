from __future__ import annotations

import os
from pathlib import Path

import pooch
from platformdirs import user_cache_dir

# ==================== 1. 统一的基础配置 ====================
DEFAULT_ENDPOINT = 'https://huggingface.co'
DEFAULT_BASE_CACHE = user_cache_dir('wulu-geetest-bypass', appauthor=False)
BASE_CACHE = Path(os.environ.get('WULU_CACHE_DIR', DEFAULT_BASE_CACHE))
ROOT = Path(__file__).resolve().parents[4]

# ==================== 2. 模型资产规范声明 ====================
MODEL_PATH = 'icon_t1_261010'


# ==================== 3. 核心加载逻辑 ====================
def _get_downloader(progressbar: bool = True) -> pooch.HTTPDownloader:
    token = os.environ.get('HF_TOKEN')
    headers = {'Authorization': f'Bearer {token.strip()}'} if token else {}
    return pooch.HTTPDownloader(progressbar=progressbar, headers=headers)


def get_fetcher() -> pooch.Pooch:
    endpoint = os.environ.get('HF_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')
    return pooch.create(
        path=BASE_CACHE,
        base_url='',
        registry={
            MODEL_PATH: 'SHA256:eedbfd46480c347a7901cad6d06637d5e4e10336bd8c496c02b3df2a1d9112c8'
        },
        urls={MODEL_PATH: f'{endpoint}/wulu007/gt/resolve/main/{MODEL_PATH}'},
    )


def _resolve_asset(rel_path: str, *env_vars: str) -> Path:
    # 1. 环境变量优先
    for env_var in env_vars:
        env_p = os.environ.get(env_var)
        if env_p and Path(env_p).is_file():
            return Path(env_p)

    # 2. 本地开发仓库路径
    local_dev_file = ROOT / 'repo' / 'gt' / rel_path
    if local_dev_file.is_file():
        return local_dev_file

    # 3. Pooch >> BASE_CACHE / rel_path
    fetcher = get_fetcher()
    # pyrefly: ignore[bad-argument-type]
    return Path(fetcher.fetch(rel_path, downloader=_get_downloader(progressbar=True)))


def get_model_path() -> Path:
    return _resolve_asset(MODEL_PATH, 'WULU_ICON_MODEL_PATH')


if __name__ == '__main__':
    print(get_model_path())
