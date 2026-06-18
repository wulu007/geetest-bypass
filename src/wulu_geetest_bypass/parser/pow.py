import hashlib
import uuid


def generate_pow(
    lot_number: str,
    captcha_id: str,
    *,
    hashfunc: str = 'md5',
    version: str = '1',
    bits: int = 10,
    datetime: str = '',
    extra: str = '',
) -> dict:
    if hashfunc not in hash_mapping:
        raise ValueError(f'Unsupported hash algorithm: {hashfunc}')
    hasher_creator = hash_mapping[hashfunc]

    remainder = bits % 4
    zero_count = bits // 4
    prefix = '0' * zero_count

    thresholds = {1: '7', 2: '3', 3: '1'}
    threshold = thresholds.get(remainder)

    header = (
        f'{version}|{bits}|{hashfunc}|{datetime}|{captcha_id}|{lot_number}|{extra}|'
    )

    while True:
        rand = str(uuid.uuid4()).replace('-', '')
        message = header + rand
        h = hasher_creator(message.encode()).hexdigest()

        # 检查是否满足工作量难度
        if not h.startswith(prefix):
            continue
        if remainder == 0:
            return {'pow_msg': message, 'pow_sign': h}
        elif h[zero_count] <= threshold:
            return {'pow_msg': message, 'pow_sign': h}


hash_mapping = {
    'md5': hashlib.md5,
    'sha1': hashlib.sha1,
    'sha256': hashlib.sha256,
}
