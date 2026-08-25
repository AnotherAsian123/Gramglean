"""Fetch full post metadata — every carousel item, never just the visible 3.

Instagram's web player virtualizes carousels: the DOM only ever contains ~3
<li> slides, so anything that scrapes rendered HTML misses most of a large
carousel. But the complete media data is always available server-side:

* Logged out: the post page embeds a Relay payload in a
  <script type="application/json"> tag whose media object carries the full
  `carousel_media` array (verified live: a 16-image post exposes all 16 with
  full-res CDN URLs). The GraphQL API itself rejects logged-out calls, so the
  embedded payload is the anonymous source of truth.
* Logged in (cookies.txt uploaded): `/api/v1/media/{pk}/info/` — the same
  private API the official web client uses — returns the identical structure
  with per-rendition width/height. The pk is derived offline from the
  shortcode (base64url), so no HTML round-trip is needed.

Both paths normalise into PostInfo/PostItem. Renditions are picked by
width*height when dimensions are present, else the first candidate (Instagram
orders candidates largest-first).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..core import config
from .urls import pk_from_shortcode


class FetchError(Exception):
    """Base: unexpected failure talking to Instagram."""


class RateLimited(FetchError):
    """Instagram asked us to slow down (HTTP 429 / 'please wait')."""


class LoginRequired(FetchError):
    """Post needs an authenticated session (private/age-gated), or the
    cookie session is dead."""


class PostUnavailable(FetchError):
    """Post deleted, id wrong, or region-blocked."""


@dataclass
class PostItem:
    index: int
    media_type: str  # image|video
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class PostInfo:
    shortcode: str
    username: Optional[str]
    caption: Optional[str]
    taken_at: Optional[datetime]
    items: list[PostItem] = field(default_factory=list)


def build_http_client(cookies: Optional[dict[str, str]] = None) -> httpx.Client:
    # Full browser-parity headers: Instagram only server-renders the media
    # payload into the page when the request looks like a real navigation
    # (verified: without Sec-Fetch-*/sec-ch-ua the response is an empty app
    # shell with no carousel data).
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if cookies:
        headers["X-IG-App-ID"] = config.IG_APP_ID
        if "csrftoken" in cookies:
            headers["X-CSRFToken"] = cookies["csrftoken"]
    return httpx.Client(
        headers=headers,
        cookies=cookies or {},
        timeout=config.REQUEST_TIMEOUT,
        follow_redirects=True,
    )


def fetch_post(client: httpx.Client, shortcode: str, authenticated: bool) -> PostInfo:
    if authenticated:
        return _fetch_via_api(client, shortcode)
    return _fetch_via_embed(client, shortcode)


# --- authenticated: private web API ---------------------------------------

def _fetch_via_api(client: httpx.Client, shortcode: str) -> PostInfo:
    pk = pk_from_shortcode(shortcode)
    url = f"https://www.instagram.com/api/v1/media/{pk}/info/"
    # XHR-style headers for the API call (the client defaults describe a
    # top-level navigation, which this is not).
    resp = client.get(url, headers={
        "Accept": "*/*",
        "Referer": f"https://www.instagram.com/p/{shortcode}/",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    })
    _raise_for_status(resp)
    try:
        payload = resp.json()
        item = payload["items"][0]
    except (ValueError, KeyError, IndexError) as exc:
        raise PostUnavailable(f"Media info API returned no item for {shortcode}") from exc
    return _normalise(item, shortcode)


# --- anonymous: embedded JSON in the post page ----------------------------

_SCRIPT_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)
_MEDIA_KEYS = ("carousel_media", "image_versions2", "video_versions")


def _fetch_via_embed(client: httpx.Client, shortcode: str) -> PostInfo:
    url = f"https://www.instagram.com/p/{shortcode}/"
    resp = client.get(url)
    _raise_for_status(resp)
    if "/accounts/login" in str(resp.url):
        raise LoginRequired(f"Instagram requires login to view {shortcode}")

    for match in _SCRIPT_RE.finditer(resp.text):
        blob = match.group(1)
        if not any(key in blob for key in _MEDIA_KEYS):
            continue
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        node = _find_media_node(data, shortcode)
        if node is not None:
            return _normalise(node, shortcode)
    raise LoginRequired(
        f"No media data embedded in the page for {shortcode} "
        "(private or login-gated post?)"
    )


def _find_media_node(data: Any, shortcode: str) -> Optional[dict]:
    """Depth-first walk for the media object matching our shortcode."""
    stack = [data]
    fallback = None
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "code" in node and any(k in node for k in _MEDIA_KEYS):
                if node.get("code") == shortcode:
                    return node
                if fallback is None:
                    fallback = node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return fallback


# --- normalisation --------------------------------------------------------

def _normalise(item: dict, shortcode: str) -> PostInfo:
    caption = item.get("caption")
    if isinstance(caption, dict):
        caption = caption.get("text")
    taken_at = item.get("taken_at")
    if isinstance(taken_at, (int, float)):
        taken_at = datetime.fromtimestamp(taken_at, tz=timezone.utc).replace(tzinfo=None)
    else:
        taken_at = None
    username = (item.get("user") or {}).get("username")

    children = item.get("carousel_media") or [item]
    items = [_normalise_child(child, idx) for idx, child in enumerate(children)]
    if not items:
        raise PostUnavailable(f"Post {shortcode} contains no downloadable media")
    return PostInfo(
        shortcode=shortcode,
        username=username,
        caption=caption,
        taken_at=taken_at,
        items=items,
    )


def _normalise_child(node: dict, index: int) -> PostItem:
    videos = node.get("video_versions") or []
    if node.get("media_type") == 2 or videos:
        best = _best(videos)
        if best is None:
            raise PostUnavailable(f"Video item {index} has no playable rendition")
        return PostItem(index, "video", best["url"], best.get("width"), best.get("height"))

    candidates = (node.get("image_versions2") or {}).get("candidates") or []
    best = _best(candidates)
    if best is None:
        raise PostUnavailable(f"Image item {index} has no rendition candidates")
    return PostItem(
        index,
        "image",
        best["url"],
        best.get("width") or node.get("original_width"),
        best.get("height") or node.get("original_height"),
    )


def _best(candidates: list[dict]) -> Optional[dict]:
    with_urls = [c for c in candidates if c.get("url")]
    if not with_urls:
        return None
    if any(c.get("width") for c in with_urls):
        return max(with_urls, key=lambda c: (c.get("width") or 0) * (c.get("height") or 0))
    # Logged-out embeds omit dimensions; Instagram lists largest first.
    return with_urls[0]


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 429:
        raise RateLimited("Instagram returned HTTP 429 (rate limited)")
    if resp.status_code in (401, 403):
        raise LoginRequired(f"Instagram returned HTTP {resp.status_code}")
    if resp.status_code == 404:
        raise PostUnavailable("Instagram returned HTTP 404 (post removed?)")
    if resp.status_code == 400:
        body = resp.text[:200].lower()
        if "login_required" in body or "checkpoint" in body or "challenge" in body:
            raise LoginRequired("Instagram session rejected (login required/challenge)")
        raise FetchError(f"Instagram returned HTTP 400: {resp.text[:200]}")
    if resp.status_code >= 500:
        raise FetchError(f"Instagram server error HTTP {resp.status_code}")
    resp.raise_for_status()
