"""Instagram URL handling.

A post is identified by its shortcode (`/p/<shortcode>/`, also under /reel/,
/reels/ or /tv/, optionally prefixed with a username). The shortcode is a
base64url encoding of the numeric media pk, which lets an authenticated
client hit the stable `/api/v1/media/{pk}/info/` endpoint directly without
ever loading the HTML page.
"""
from __future__ import annotations

import re
import string
from urllib.parse import urlparse

_SHORTCODE_RE = re.compile(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,39})(?:[/?]|$)")
_HOSTS = ("instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am")
_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_"


class InvalidLink(ValueError):
    pass


def shortcode_from_url(url: str) -> str:
    """Extract the shortcode from any Instagram post/reel URL form."""
    raw = url.strip()
    if not raw:
        raise InvalidLink("Empty link.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in _HOSTS:
        raise InvalidLink(f"Not an Instagram link: {url.strip()!r}")
    match = _SHORTCODE_RE.search(parsed.path)
    if not match:
        raise InvalidLink(f"No post found in link: {url.strip()!r}")
    return match.group(1)


def pk_from_shortcode(shortcode: str) -> int:
    """Decode a shortcode to its numeric media pk (base64url, big-endian).

    Only the first 11 characters encode the pk; longer "share" codes append
    junk that must be ignored.
    """
    pk = 0
    for ch in shortcode[:11]:
        pk = pk * 64 + _ALPHABET.index(ch)
    return pk
