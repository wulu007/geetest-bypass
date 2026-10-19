from __future__ import annotations

import os
from pathlib import Path

import pooch
from platformdirs import user_cache_dir

DEFAULT_ENDPOINT = 'https://huggingface.co'
ENDPOINT = os.environ.get('HF_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')
BASE_CACHE = Path(user_cache_dir('wulu-geetest-bypass', appauthor=False))
TYPE = 'nine'
ROOT = Path(__file__).resolve().parents[4]


def _get_downloader(progressbar: bool = True) -> pooch.HTTPDownloader:
    token = os.environ.get('HF_TOKEN')
    headers = {'Authorization': f'Bearer {token.strip()}'} if token else {}
    return pooch.HTTPDownloader(progressbar=progressbar, headers=headers)


def get_fetcher():
    return pooch.create(
        path=BASE_CACHE / TYPE,
        base_url=f'{ENDPOINT}/wulu007/gt2/resolve/main/261019',
        registry={
            'nine.onnx': 'SHA256:d08f8c4468a581ea1390c63e70c5a7e49406975dbbd6db52d7af36f1e5831090',
        },
    )


def get_model_path() -> Path:
    env_p = os.environ.get('NINE_MODEL_PATH')
    if env_p and Path(env_p).is_file():
        return Path(env_p)

    local = ROOT / 'repo' / 'gt2' / '261019' / 'nine.onnx'
    if local.is_file():
        return local

    return Path(
        # pyrefly: ignore[bad-argument-type]
        get_fetcher().fetch('nine.onnx', downloader=_get_downloader(progressbar=True))
    )


if __name__ == '__main__':
    print(f'Model: {get_model_path()}')
