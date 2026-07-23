import asyncio

import pytest

from wulu_geetest_bypass import Geetest

test_risk = ['ai', 'slide', 'match', 'winlinze', 'svg_seed', 'svg_icon']
captcha_id = '54088bb07d2df3c46b79f80300b0abbe'


@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', test_risk)
async def test_risk_type(risk_type):
    g = Geetest(captcha_id=captcha_id, risk_type=risk_type)
    result = await g.resolve()
    assert result is not None


@pytest.mark.asyncio
async def test_slide():
    g = Geetest(captcha_id=captcha_id, risk_type='slide')
    total = 50
    success = 0
    tasks = [g.resolve(1) for _ in range(total)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if not isinstance(r, Exception))
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f'Task {i} Error: {r}')
    print(f'Success: {success}/{total}')


test_lang = [
    'ara',
    'deu',
    'eng',
    'fra',
    'ind',
    'jpn',
    'kor',
    'por',
    'rus',
    'spa',
    'zho-hk',
    'zho',
]


@pytest.mark.asyncio
@pytest.mark.parametrize('lang', test_lang)
async def test_voice(lang):
    g = Geetest(captcha_id=captcha_id, risk_type='slide', lang=lang, voice=True)
    result = await g.resolve(1)
    assert result is not None
