"""At-rest encryption for cookie files (AES-256-GCM).

The key comes from the ``COOKIE_ENCRYPTION_KEY`` environment variable, set on the
container (e.g. in the Unraid template) and therefore kept OUT of the appdata
share — so a leaked or backed-up ``/config`` folder alone cannot decrypt the
cookies. If the variable is unset, cookies are stored as plaintext (protected
only by file permissions) and everything still works.

Accepted key formats for the env var:
  * a urlsafe-base64 string decoding to exactly 32 bytes (preferred), or
  * any other string, from which a 32-byte key is derived via SHA-256.

Generate a strong key with:
  python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Marks an encrypted blob so we can transparently read mixed plaintext/encrypted
# files (e.g. cookies uploaded before a key was configured).
_MAGIC = b"AGCM1"
_NONCE_LEN = 12


def _load_key() -> Optional[bytes]:
    raw = os.getenv("COOKIE_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    # Prefer a real 32-byte base64 key.
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(decoded) == 32:
            return decoded
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        pass
    # Otherwise derive a 32-byte key from the provided secret.
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encryption_enabled() -> bool:
    return _load_key() is not None


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(_MAGIC)


def encrypt(data: bytes) -> bytes:
    """Encrypt if a key is configured; otherwise return the data unchanged."""
    key = _load_key()
    if key is None:
        return data
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return _MAGIC + nonce + ciphertext


def decrypt(blob: bytes) -> bytes:
    """Decrypt an encrypted blob; pass plaintext through untouched.

    Raises if the blob is encrypted but no/incorrect key is configured.
    """
    if not is_encrypted(blob):
        return blob
    key = _load_key()
    if key is None:
        raise ValueError(
            "Cookie is encrypted but COOKIE_ENCRYPTION_KEY is not set."
        )
    nonce = blob[len(_MAGIC) : len(_MAGIC) + _NONCE_LEN]
    ciphertext = blob[len(_MAGIC) + _NONCE_LEN :]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
