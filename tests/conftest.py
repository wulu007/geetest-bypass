from pathlib import Path

import pytest


@pytest.fixture
def cid() -> str:
    return '54088bb07d2df3c46b79f80300b0abbe'


@pytest.fixture
def out_dir():
    return Path(__file__).parent / 'resources'
