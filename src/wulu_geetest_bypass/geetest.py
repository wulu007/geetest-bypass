import json
import random
import time
import uuid
from typing import Unpack

from wreq import Client, Emulation

from ._exceptions import VerifyError
from ._type import GeetestOptions, Seccode, VerifyResponse, WPayload
from .config import Config
from .crypto import build_w
from .parser import generate_pow, parse_abo_pair
from .solver.match import solve_match
from .solver.winlinze import solve_winlinze


def _callback() -> str:
    return f'geetest_{int(time.time() * 1000)}'


def _unwrap_jsonp(text: str) -> dict:
    t = text.strip()
    if '(' in t:
        t = t[t.index('(') + 1 : t.rindex(')')]
    return json.loads(t)


class Geetest:
    BASE_URL = 'https://gcaptcha4.geetest.com'
    IMG_BASE = 'https://static.geetest.com'

    def __init__(self, **kwargs: Unpack[GeetestOptions]):
        self.captcha_id = kwargs['captcha_id']
        self.risk_type = kwargs.get('risk_type', 'ai')
        self.client_type = kwargs.get('client_type', 'web')
        self.proxy = kwargs.get('proxy')
        self.client = kwargs.get(
            'client',
            Client(
                emulation=Emulation.random(),
                headers={
                    'Accept': '*/*',
                    'Sec-Fetch-Site': 'same-site',
                    'Sec-Fetch-Mode': 'no-cors',
                    'Sec-Fetch-Dest': 'script',
                    'sec-ch-ua-mobile': '?0',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                },
            ),
        )
        self.lang = kwargs.get('lang', 'zh')

    async def load(self):
        params = {
            'callback': _callback(),
            'captcha_id': self.captcha_id,
            'challenge': str(uuid.uuid4()),
            'client_type': self.client_type,
            'risk_type': self.risk_type,
            'lang': self.lang,
        }
        try:
            resp = await self.client.get(f'{self.BASE_URL}/load', query=params)
            data = _unwrap_jsonp(await resp.text())
        except Exception as e:
            raise RuntimeError(f'load request failed: {e}') from e

        d = data.get('data')
        if not isinstance(d, dict):
            raise RuntimeError('load response missing data field')
        return d

    async def _load_img(self, path: str) -> bytes:
        try:
            resp = await self.client.get(f'{self.IMG_BASE}/{path}')
            return await resp.bytes()
        except Exception as e:
            raise RuntimeError(f'load_img request failed: {e}') from e

    async def verify(self, data) -> VerifyResponse:
        if data['captcha_type'] == 'slide':
            data['bg'] = await self._load_img(data['bg'])
            data['slice'] = await self._load_img(data['slice'])

        data.setdefault('captcha_id', self.captcha_id)

        base = {
            'callback': _callback(),
            'captcha_id': self.captcha_id,
            'client_type': self.client_type,
            'risk_type': data['captcha_type'],
            'lot_number': data['lot_number'],
            'payload': data['payload'],
            'process_token': data['process_token'],
            'payload_protocol': data['payload_protocol'],
            'pt': data['pt'],
            'w': Geetest.generate_w(**data),
        }

        try:
            resp = await self.client.get(f'{self.BASE_URL}/verify', query=base)
            data = _unwrap_jsonp(await resp.text())
        except Exception as e:
            raise RuntimeError(f'verify request failed: {e}') from e

        return data

    async def resolve(self, retry: int = 3) -> Seccode:
        for attempt in range(retry):
            data = await self.load()
            data = (await self.verify(data))['data']
            if data['result'] == 'success':
                return data['seccode']
            if attempt < retry - 1:
                continue
            raise VerifyError(f'verification failed after {retry} attempts: {data}')

    @staticmethod
    def generate_w(**data: Unpack[WPayload]) -> str:
        lot_number = data['lot_number']
        pow_detail = data['pow_detail']
        payload = {
            **generate_pow(lot_number, data['captcha_id'], **pow_detail),
            **parse_abo_pair(Config.abo_key, Config.abo_val, lot_number),
            Config.lib_key: Config.lib_val,
            'biht': Config.biht,
            'device_id': '',
            'em': Config.em,
            'ep': '123',
            'geetest': 'captcha',
            'lang': 'zh',
            'lot_number': lot_number,
        }

        if data['guard']:
            payload.update(Config.gee_guard)

        ct = data['captcha_type']
        if ct == 'ai':
            pass
        elif ct == 'slide':
            from .solver.slide import solve_slide

            set_left = solve_slide(data['bg'], data['slice'], int(data['ypos']))
            payload['setLeft'] = set_left
            payload['userresponse'] = set_left / 1.0059466666666665 + 2
            payload['passtime'] = random.randint(600, 1400)
        elif ct == 'svg_seed':
            from .solver.svg_seed import solve_svg

            layer, point = solve_svg(data['question_path'], data['answer_path'])
            frame = [0, 2248, 4970, 7642]
            payload['userresponse'] = point
            payload['passtime'] = random.randint(frame[layer] + 500, frame[layer + 1])
        elif ct == 'match':
            payload['userresponse'] = solve_match(data['ques'])
            payload['passtime'] = random.randint(600, 1400)
        elif ct == 'winlinze':
            payload['userresponse'] = solve_winlinze(data['ques'])
            payload['passtime'] = random.randint(600, 1400)

        else:
            raise NotImplementedError(f'risk_type {ct} not implemented')

        return build_w(json.dumps(payload, separators=(',', ':')), int(data['pt']))
