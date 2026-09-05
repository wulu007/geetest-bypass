import base64
import gzip
import json
import time
import zlib
from typing import Any


def track_zip(track_data: Any, mtime: int | None = None) -> str:
    """
    Compress track data the same way gg4.js does: fflate ``gzipSync`` + urlsafe base64.

    The gzip header is assembled by hand to match fflate byte for byte -- fflate
    hardcodes OS 3 (Unix) and writes ``Date.now() / 1000`` as mtime, while :mod:`gzip`
    would emit OS 255 (unknown). The deflate stream itself still differs, since zlib
    and fflate are separate implementations.

    :param track_data: The track data to compress.
    :param mtime: Modification time in the gzip header; defaults to the current time.
    :return: The urlsafe base64 encoded gzip blob, without padding.
    """
    json_str = json.dumps(track_data, separators=(',', ':'), ensure_ascii=False)
    json_bytes = json_str.encode('utf-8')
    compressor = zlib.compressobj(6, zlib.DEFLATED, -zlib.MAX_WBITS)
    deflated = compressor.compress(json_bytes) + compressor.flush()
    compressed = (
        b'\x1f\x8b\x08\x00'  # magic, deflate, no flags
        + (int(time.time()) if mtime is None else mtime).to_bytes(4, 'little')
        + b'\x00\x03'  # XFL 0 (level 6), OS 3 (Unix)
        + deflated
        + (zlib.crc32(json_bytes) & 0xFFFFFFFF).to_bytes(4, 'little')
        + (len(json_bytes) & 0xFFFFFFFF).to_bytes(4, 'little')
    )
    b64_encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
    return b64_encoded.rstrip('=')


def track_unzip(encoded_str: str) -> Any:
    padding = '=' * (-len(encoded_str) % 4)  # Add padding if necessary
    b64_decoded = base64.urlsafe_b64decode(encoded_str + padding)
    decompressed = gzip.decompress(b64_decoded)
    json_str = decompressed.decode('utf-8')
    return json.loads(json_str)
