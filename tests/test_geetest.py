import asyncio

import pytest

from wulu_geetest_bypass import Geetest

test_risk = ['ai', 'slide', 'match', 'winlinze', 'svg_seed']


@pytest.mark.asyncio
@pytest.mark.parametrize('risk_type', test_risk)
async def test_risk_type(risk_type):
    g = Geetest(captcha_id='54088bb07d2df3c46b79f80300b0abbe', risk_type=risk_type)
    result = await g.resolve()
    assert result is not None


@pytest.mark.asyncio
async def test_slide():
    g = Geetest(captcha_id='54088bb07d2df3c46b79f80300b0abbe', risk_type='slide')
    total = 50
    success = 0
    tasks = [g.resolve() for _ in range(total)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if not isinstance(r, Exception))
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f'Task {i} Error: {r}')
    print(f'Success: {success}/{total}')
