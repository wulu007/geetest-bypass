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
TYPE = 'phrase'
VERSION = '261013'
ORDER_PATH = f'{TYPE}/{VERSION}/order.onnx'
DETECT_PATH = f'{TYPE}/{VERSION}/detect.onnx'
TOKENIZER_PATH = f'{TYPE}/{VERSION}/tokenizer.json'
DICT_PATH = f'{TYPE}/{VERSION}/dict.json'


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
            ORDER_PATH: 'SHA256:3d4c93760e9c7a1113ee987ed36ecb409a3cf148a50f6dde9fe9616d6296c9c4',
            DETECT_PATH: 'SHA256:f5b75b31d35a37076feefa1bc7ebc4381bb096bf87b100bda341675467aa8f80',
            TOKENIZER_PATH: 'SHA256:ea906002125edc849e0946e1528f91d72de4fbe9767d3af5879a44e229035b37',
            DICT_PATH: 'SHA256:672510c09114f4f6cb338731ad0c22efbb629ff8dbe4e6f291f04c2296b258a9',
        },
        urls={
            ORDER_PATH: f'{endpoint}/wulu007/gt/resolve/main/{ORDER_PATH}',
            DETECT_PATH: f'{endpoint}/wulu007/gt/resolve/main/{DETECT_PATH}',
            TOKENIZER_PATH: f'{endpoint}/wulu007/gt/resolve/main/{TOKENIZER_PATH}',
            DICT_PATH: f'{endpoint}/wulu007/gt/resolve/main/{DICT_PATH}',
        },
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


def get_order_model_path() -> Path:
    return _resolve_asset(ORDER_PATH, 'WULU_PHRASE_ORDER_PATH')


def get_detect_model_path() -> Path:
    return _resolve_asset(DETECT_PATH, 'WULU_PHRASE_DETECT_PATH')


def get_tokenizer_path() -> Path:
    return _resolve_asset(TOKENIZER_PATH, 'WULU_PHRASE_TOKENIZER_PATH')


def get_dict_path() -> Path:
    return _resolve_asset(DICT_PATH, 'WULU_PHRASE_DICT_PATH')


if __name__ == '__main__':
    for name in (
        ORDER_PATH,
        DETECT_PATH,
        TOKENIZER_PATH,
        DICT_PATH,
    ):
        print(f'{name}: {_resolve_asset(name)}')
