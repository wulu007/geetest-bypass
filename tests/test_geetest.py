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
    for _ in range(total):
        try:
            await g.resolve()
            success += 1
        except Exception as e:
            print(f'Error: {e}')

    print(f'Success: {success}/{total}')
