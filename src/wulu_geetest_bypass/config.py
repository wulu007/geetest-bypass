from typing import ClassVar


class Config:
    gee_guard: ClassVar = {
        'roe': {
            'aup': '3',
            'sep': '3',
            'egp': '3',
            'auh': '3',
            'rew': '3',
            'snh': '3',
            'res': '3',
            'cdc': '3',
        }
    }

    em: ClassVar = {
        'cp': 0,
        'ek': '11',
        'nt': 0,
        'ph': 0,
        'sc': 0,
        'si': 0,
        'wd': 1,
    }

    biht = '1426265548'
    lib_key = 'dQFB'
    lib_val = 'BoHp'
    abo_key = '(n[5:7]+n[7:9])+.+(n[20:27])+.+(n[10:10]+n[12:12]+n[3:3]+n[7:7])'
    abo_val = 'n[7:14]'
