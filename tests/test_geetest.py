import asyncio

import pytest

from wulu_geetest_bypass import Geetest

test_risk = ['ai', 'slide', 'match', 'winlinze', 'svg_seed', 'svg_icon']


@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', test_risk)
async def test_risk_type(risk_type, cid):
    g = Geetest(captcha_id=cid, risk_type=risk_type)
    result = await g.resolve()
    assert result is not None


def test_clicks_to_userresponse():
    clicks = [(0.7483, 0.2174), (0.1417, 0.5472), (0.305, 0.4473)]
    assert Geetest._clicks_to_userresponse(clicks) == [
        [7483, 2174],
        [1417, 5472],
        [3050, 4473],
    ]


def test_auto_solve_icon_click():
    Geetest._solvers['icon'] = lambda imgs, ques: [(0.75, 0.2), (0.3, 0.5), (0.1, 0.8)]
    try:
        data = {
            'captcha_type': 'icon',
            'imgs': b'x',
            'ques': [b'a', b'b', b'c'],
        }
        ans = Geetest.auto_solve(data)
        assert ans['userresponse'] == [[7500, 2000], [3000, 5000], [1000, 8000]]
        assert 'track' in ans and 'passtime' in ans
        assert ans['passtime'] > 0
    finally:
        del Geetest._solvers['icon']


@pytest.mark.asyncio
async def test_slide(cid):
    g = Geetest(captcha_id=cid, risk_type='slide')
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
async def test_voice(lang, cid):
    pytest.importorskip('miniaudio')
    pytest.importorskip('wulu_geetest_bypass_voice')
    g = Geetest(captcha_id=cid, risk_type='slide', lang=lang, voice=True)
    result = await g.resolve(1)
    assert result is not None
