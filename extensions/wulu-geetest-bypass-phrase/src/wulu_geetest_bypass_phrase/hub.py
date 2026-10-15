from __future__ import annotations

import os
from pathlib import Path

import pooch
from platformdirs import user_cache_dir

DEFAULT_ENDPOINT = 'https://huggingface.co'
ENDPOINT = os.environ.get('HF_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')
BASE_CACHE = Path(user_cache_dir('wulu-geetest-bypass', appauthor=False))
TYPE = 'phrase'


def get_fetcher():
    return pooch.create(
        path=BASE_CACHE / TYPE,
        base_url=f'{ENDPOINT}/wulu007/gt/resolve/main/{TYPE}/261013',
        registry={
            'order.onnx': 'SHA256:3d4c93760e9c7a1113ee987ed36ecb409a3cf148a50f6dde9fe9616d6296c9c4',
            'detect.onnx': 'SHA256:f5b75b31d35a37076feefa1bc7ebc4381bb096bf87b100bda341675467aa8f80',
            'tokenizer.json': 'SHA256:ea906002125edc849e0946e1528f91d72de4fbe9767d3af5879a44e229035b37',
            'dict.json': 'SHA256:672510c09114f4f6cb338731ad0c22efbb629ff8dbe4e6f291f04c2296b258a9',
        },
    )


def get_order_model_path() -> Path:
    local_file = get_fetcher().fetch('order.onnx', progressbar=True)
    return Path(local_file)


def get_detect_model_path() -> Path:
    local_file = get_fetcher().fetch('detect.onnx', progressbar=True)
    return Path(local_file)


def get_tokenizer_path() -> Path:
    local_file = get_fetcher().fetch('tokenizer.json', progressbar=True)
    return Path(local_file)


def get_dict_path() -> Path:
    local_file = get_fetcher().fetch('dict.json', progressbar=True)
    return Path(local_file)


if __name__ == '__main__':
    for file in ['order.onnx', 'detect.onnx', 'tokenizer.json', 'dict.json']:
        local_file = get_fetcher().fetch(file, progressbar=True)
        print(f'Fetched {file} to {local_file}')
