# Copyright (c) 2026 wulu007
# SPDX-License-Identifier: MIT

from random import choice

_UNIVERSAL_GPUS = (
    ('NVIDIA', 'NVIDIA GeForce RTX 4060', '0x00002882'),
    ('NVIDIA', 'NVIDIA GeForce RTX 4060 Laptop GPU', '0x000028E0'),
    ('NVIDIA', 'NVIDIA GeForce RTX 3060', '0x00002504'),
    ('NVIDIA', 'NVIDIA GeForce RTX 3060 Laptop GPU', '0x00002520'),
    ('Intel', 'Intel(R) Iris(R) Xe Graphics', '0x00009A49'),
    ('Intel', 'Intel(R) Iris(R) Xe Graphics', '0x0000A7A0'),
    ('Intel', 'Intel(R) UHD Graphics 770', '0x00004680'),
    ('AMD', 'AMD Radeon 780M Graphics', '0x00001900'),
    ('AMD', 'AMD Radeon 680M Graphics', '0x00001681'),
)
_SUFFIX = ' Direct3D11 vs_5_0 ps_5_0, D3D11)'
WEBGL_RENDERERS = tuple(
    f'ANGLE ({vendor}, {name} ({device_id}){_SUFFIX}'
    for vendor, name, device_id in _UNIVERSAL_GPUS
)

_CORES = (12, 16)
_MEMORY = (8, 16)
_RESOLUTIONS = ((1920, 1080), (1920, 1200), (2560, 1440), (2560, 1600))
FP_VERSION = 1


def webgl_renderer() -> str:
    """Return a random ANGLE D3D11 WebGL renderer string."""
    return choice(WEBGL_RENDERERS)


def gen_ce(version: int = FP_VERSION) -> dict:
    """Build a Windows Chrome ``ce`` (CloudEnvironment) snapshot payload."""
    return {
        'v': version,
        'g1': choice(_CORES),  # navigator.hardwareConcurrency
        'g2': choice(_MEMORY),  # navigator.deviceMemory
        'g3': choice(_RESOLUTIONS),  # [max, min] of screen width/height
        'g8': 'Win32',  # navigator.platform, consistent with D3D11 renderers above
        'g17': {'v5': webgl_renderer()},  # UNMASKED_RENDERER_WEBGL
        's': {'g1': 0, 'g2': 0, 'g3': 0, 'g8': 0, 'g17': 0},  # status: 0 = OK
    }
