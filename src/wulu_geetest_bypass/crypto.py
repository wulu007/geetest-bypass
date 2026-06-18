import base64
import os

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util import Padding
from smcryptopy import sm2, sm4

RSA_N_HEX = (
    '00C1E3934D1614465B33053E7F48EE4EC87B14B95EF88947713D25EECBFF7E74'
    'C7977D02DC1D9451F79DD5D1C10C29ACB6A9B4D6FB7D0A0279B6719E1772565F'
    '09AF627715919221AEF91899CAE08C0D686D748B20A3603BE2318CA6BC2B5970'
    '6592A9219D0BF05C9F65023A21D2330807252AE0066D59CEEFA5F2748EA80BAB81'
)
RSA_KEY = RSA.construct((int(RSA_N_HEX, 16), 0x10001))

SM2_PUBKEY_X = '9a4ea935b2576f37516d9b29cd8d8cc9bffe548ba6853253ba20f4ba44fba8c9'
SM2_PUBKEY_Y = 'e97a398882769aa0dd1e3e1b5601429287303880ca17bd244ed73bf702a68fc7'


def guid() -> str:
    return os.urandom(8).hex()


def encrypt_pt0(plaintext: str) -> str:
    return base64.urlsafe_b64encode(plaintext.encode()).decode()


def encrypt_pt1(plaintext: str) -> str:
    key_bytes = guid().encode()
    padded = Padding.pad(plaintext.encode(), AES.block_size, style='pkcs7')
    iv = b'0' * 16
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv).encrypt(padded)
    enc_key = PKCS1_v1_5.new(RSA_KEY).encrypt(key_bytes)
    return cipher.hex() + enc_key.hex()


def encrypt_pt2(plaintext: str) -> str:
    key_bytes = guid().encode()
    cipher = sm4.encrypt_cbc(plaintext.encode(), key_bytes, b'0' * 16)
    pk = SM2_PUBKEY_X + SM2_PUBKEY_Y
    enc_key = sm2.encrypt_c1c2c3(key_bytes, pk).hex()
    return cipher.hex() + enc_key


def build_w(plaintext: str, pt: int) -> str:
    if pt == 0:
        return encrypt_pt0(plaintext)
    elif pt == 1:
        return encrypt_pt1(plaintext)
    elif pt == 2:
        return encrypt_pt2(plaintext)
    raise ValueError(f'unknown pt: {pt}')
