"""Optional at-rest encryption for cookie files (AES-256-GCM).

Wire format: b"AGCM1" magic + 12-byte nonce + ciphertext. Plaintext and
encrypted files coexist transparently: decrypt() passes non-magic bytes
through untouched, so setting or unsetting the key never breaks reads of
files written the other way (an encrypted file without the key raises).

Key: COOKIE_ENCRYPTION_KEY env var. If it urlsafe-base64-decodes to exactly
32 bytes it is used directly; otherwise the passphrase is stretched with
scrypt (n=2**14) using a fixed application salt.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_MAGIC = b"AGCM1"
_SALT = b"gramglean-cookie-key-v1"


class DecryptionError(Exception):
    pass


def _load_key() -> bytes | None:
    raw = os.getenv("COOKIE_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw.encode())
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    kdf = Scrypt(salt=_SALT, length=32, n=2**14, r=8, p=1)
    return kdf.derive(raw.encode())


_KEY = _load_key()


def encryption_enabled() -> bool:
    return _KEY is not None


def encrypt(data: bytes) -> bytes:
    if _KEY is None:
        return data
    nonce = os.urandom(12)
    return _MAGIC + nonce + AESGCM(_KEY).encrypt(nonce, data, None)


def is_encrypted(data: bytes) -> bool:
    return data.startswith(_MAGIC)


def decrypt(data: bytes) -> bytes:
    if not is_encrypted(data):
        return data
    if _KEY is None:
        raise DecryptionError("File is encrypted but COOKIE_ENCRYPTION_KEY is not set.")
    nonce, ct = data[len(_MAGIC):len(_MAGIC) + 12], data[len(_MAGIC) + 12:]
    try:
        return AESGCM(_KEY).decrypt(nonce, ct, None)
    except Exception as exc:
        raise DecryptionError("Cookie file could not be decrypted (wrong key?).") from exc
