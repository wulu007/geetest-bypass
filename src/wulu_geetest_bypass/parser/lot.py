def parse_lot_string(pattern: str) -> list:
    result = []
    for part in pattern.split('+.+'):
        group = []
        for single in part.split('+'):
            start_idx = single.index('[') + 1
            end_idx = single.index(']')
            inner = single[start_idx:end_idx]
            bounds = [int(n) for n in inner.split(':')]
            group.append(bounds)
        result.append(group)
    return result


def get_string_by_indexes(indexes: list, s: str) -> str:
    parts = []
    for group in indexes:
        group_str = ''
        for r in group:
            start = r[0]
            end = r[1] + 1 if len(r) > 1 else start + 1
            group_str += s[start:end]
        parts.append(group_str)
    return '.'.join(parts)


def parse_abo_pair(key: str, value: str, lot_number: str) -> dict:
    key_str = get_string_by_indexes(parse_lot_string(key), lot_number)
    val_str = get_string_by_indexes(parse_lot_string(value), lot_number)

    parts = key_str.split('.')
    obj = {}
    current = obj
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    if parts:
        current[parts[-1]] = val_str
    return obj
