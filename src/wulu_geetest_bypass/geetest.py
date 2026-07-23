import json
import random
import time
import uuid
from typing import Unpack

from wreq import Client, Emulation

from ._exceptions import VerifyError
from ._type import (
    GeetestOptions,
    RiskType,
    Seccode,
    VerifyResponse,
    WPayload,
)
from .config import Config
from .crypto import build_w
from .parser import generate_pow, parse_abo_pair
from .solver import solve_match, solve_slide, solve_svg, solve_winlinze


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

    default_headers = {
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Dest': 'script',
        'sec-ch-ua-mobile': '?0',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'referer': 'https://www.geetest.com/',
    }

    _solvers = {
        'ai': lambda: None,
        'slide': solve_slide,
        'svg_seed': solve_svg,
        'svg_icon': solve_svg,
        'match': solve_match,
        'winlinze': solve_winlinze,
    }

    def __init__(self, **kwargs: Unpack[GeetestOptions]):
        self.captcha_id = kwargs['captcha_id']
        self.risk_type = kwargs.get('risk_type', 'ai')
        self.client_type = kwargs.get('client_type', 'web')
        self.lang = kwargs.get('lang', 'zh')
        if 'client' in kwargs:
            self.client = kwargs['client']
        else:
            client_options = kwargs.get('client_options', {}).copy()
            user_headers = client_options.get('headers', {})
            client_options['headers'] = {**self.default_headers, **user_headers}  # type: ignore
            client_options.setdefault('emulation', Emulation.Chrome147)
            self.client = Client(**client_options)

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
        elif data['captcha_type'] == 'svg_icon':
            data['question_path'] = (
                await self._load_img(data['question_path'])
            ).decode()
            data['answer_path'] = await self._load_img(data['answer_path'])
        elif data['captcha_type'] in ('icon', 'word', 'nine'):
            data['imgs'] = await self._load_img(data['imgs'])
            data['ques'] = [await self._load_img(url) for url in data['ques']]
        elif data['captcha_type'] in ('phrase', 'space', 'pencil'):
            data['imgs'] = await self._load_img(data['imgs'])
        elif data['captcha_type'] == 'voice':
            data['voice_audio'] = await self._load_img(data['voice_path'])

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
            'w': Geetest.generate_w(data),
        }

        try:
            resp = await self.client.get(f'{self.BASE_URL}/verify', query=base)
            data = _unwrap_jsonp(await resp.text())
        except Exception as e:
            raise RuntimeError(f'verify request failed: {e}') from e

        return data  # type: ignore

    async def resolve(self, retry: int = 3) -> Seccode:  # type: ignore
        for attempt in range(retry):
            data = await self.load()
            data = (await self.verify(data))['data']
            if data['result'] == 'success':
                return data['seccode']
            if attempt < retry - 1:
                continue
        raise VerifyError(f'verification failed after {retry} attempts: {data}')

    @staticmethod
    def generate_w(data: WPayload) -> str:
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
        solver = Geetest._solvers.get(ct)
        if solver is None:
            raise NotImplementedError(f'risk_type {ct} not implemented')

        match data['captcha_type']:
            case 'ai':
                pass
            case 'slide':
                set_left = solver(data['bg'], data['slice'], int(data['ypos']))
                payload['setLeft'] = set_left
                payload['userresponse'] = set_left / 1.0059466666666665 + 2
                payload['passtime'] = random.randint(600, 1400)
            case 'svg_seed' | 'svg_icon':
                layer, point = solver(data['question_path'], data['answer_path'])
                frame = [0, 2248, 4970, 7642]
                payload['userresponse'] = point
                payload['passtime'] = random.randint(
                    frame[layer] + 500, frame[layer + 1]
                )
            case 'match' | 'winlinze':
                payload['userresponse'] = solver(data['ques'])
                payload['passtime'] = random.randint(600, 1400)
            case 'icon' | 'word':
                payload['userresponse'] = solver(data['imgs'], data['ques'])
                payload['passtime'] = random.randint(1000, 2000)
            case 'nine':
                payload['userresponse'] = solver(
                    data['imgs'], data['ques'], data['nine_nums']
                )
                payload['passtime'] = random.randint(1000, 2000)
            case 'phrase' | 'space' | 'pencil':
                payload['userresponse'] = solver(data['imgs'])
                payload['passtime'] = random.randint(1000, 2000)
            case 'voice':
                payload['userresponse'] = solver(data['voice_audio'])
                payload['passtime'] = random.randint(20000, 30000)
            case _:
                raise NotImplementedError(
                    f'risk_type {data["captcha_type"]} not implemented'
                )

        return build_w(json.dumps(payload, separators=(',', ':')), int(data['pt']))

    @classmethod
    def register_solver(cls, risk: RiskType, solver):
        cls._solvers[risk] = solver
