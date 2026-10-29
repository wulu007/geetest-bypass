from __future__ import annotations

import os
from pathlib import Path

import pooch
from platformdirs import user_cache_dir

# ==================== 1. 统一的基础配置 ====================
DEFAULT_ENDPOINT = 'https://huggingface.co'
ENDPOINT = os.environ.get('HF_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')
DEFAULT_BASE_CACHE = user_cache_dir('wulu-geetest-bypass', appauthor=False)
BASE_CACHE = Path(os.environ.get('WULU_CACHE_DIR', DEFAULT_BASE_CACHE))
ROOT = Path(__file__).resolve().parents[4]

# ==================== 2. 模型资产规范声明 ====================
TYPE = 'yolo-text'
LOCATE_VERSION = '261028'
LOCATE_REL_PATH = f'{TYPE}/{LOCATE_VERSION}/locate.onnx'
REC_REL_PATH = '_shared/ocr/ppocrv6_rec.onnx'

REGISTRY = {
    LOCATE_REL_PATH: 'SHA256:7c576268d6c8a4ced7e9248df569378bb971fd666c974b11816fb915230e0519',
    REC_REL_PATH: 'SHA256:5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634',
}

URLS = {
    LOCATE_REL_PATH: f'{ENDPOINT}/wulu007/gt/resolve/main/{LOCATE_REL_PATH}',
    REC_REL_PATH: f'{ENDPOINT}/PaddlePaddle/PP-OCRv6_small_rec_onnx/resolve/main/inference.onnx',
}

CHECKOUT_REPO = {
    LOCATE_REL_PATH: 'gt',
    REC_REL_PATH: 'gt',
}


# ==================== 3. 核心加载逻辑 ====================
def _get_downloader(progressbar: bool = True) -> pooch.HTTPDownloader:
    token = os.environ.get('HF_TOKEN')
    headers = {'Authorization': f'Bearer {token.strip()}'} if token else {}
    return pooch.HTTPDownloader(progressbar=progressbar, headers=headers)


def get_fetcher() -> pooch.Pooch:
    return pooch.create(path=BASE_CACHE, base_url='', registry=REGISTRY, urls=URLS)


def _resolve_asset(rel_path: str, *env_vars: str) -> Path:
    # 1. 环境变量优先
    for env_var in env_vars:
        env_p = os.environ.get(env_var)
        if env_p and Path(env_p).is_file():
            return Path(env_p)

    # 2. 本地开发仓库路径
    local_dev_file = ROOT / 'repo' / CHECKOUT_REPO[rel_path] / rel_path
    if local_dev_file.is_file():
        return local_dev_file

    # 3. Pooch >> BASE_CACHE / rel_path
    fetcher = get_fetcher()
    # pyrefly: ignore[bad-argument-type]
    return Path(fetcher.fetch(rel_path, downloader=_get_downloader(progressbar=True)))


# ==================== 4. 业务暴露接口 ====================
def get_locate_model_path() -> Path:
    return _resolve_asset(LOCATE_REL_PATH, 'WULU_WORD_LOCATE_PATH')


def get_rec_model_path() -> Path:
    return _resolve_asset(REC_REL_PATH, 'WULU_WORD_OCR_PATH')


if __name__ == '__main__':
    print(f'LOCATE: {get_locate_model_path()}')
    print(f'REC:    {get_rec_model_path()}')
