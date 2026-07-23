from importlib.resources import files

import numpy as np


def load_templates(
    lang: str,
) -> tuple[np.ndarray, np.ndarray, int, str, np.ndarray]:
    path = files('wulu_geetest_bypass_voice').joinpath(f'{lang}.npz')
    data = np.load(str(path))
    return (
        data['X'],
        data['y'],
        int(data['sr']),
        str(data['lang']),
        data['prompt'],
    )


__all__ = ['load_templates']
