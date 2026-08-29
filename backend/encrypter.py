import os
import hashlib

def crypt(data: bytes, password: str, offset: int = 0) -> bytes:
    result = bytearray()
    for i, byte in enumerate(data):
        key_byte = hashlib.sha256(
            f"{password}:{offset + i}".encode()
        ).digest()[0]

        result.append(byte ^ key_byte)

    return bytes(result)
