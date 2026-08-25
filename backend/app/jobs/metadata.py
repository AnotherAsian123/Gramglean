"""Embed post metadata directly into downloaded JPEGs — losslessly.

piexif.insert() splices an APP1 EXIF segment into the file without touching
the compressed image data, so the pixels stay byte-identical to what
Instagram served. Standard fields (DateTimeOriginal, Artist,
ImageDescription) are what photo managers read for timelines and search; the
complete metadata payload also goes into UserComment as JSON.

Videos and non-JPEG files can't be embedded this way and keep a .json
sidecar instead (see runner._save_metadata).
"""
from __future__ import annotations

import json
from pathlib import Path

import piexif
import piexif.helper

from ..insta.client import PostInfo, PostItem


def metadata_payload(info: PostInfo, item: PostItem) -> dict:
    return {
        "shortcode": info.shortcode,
        "child_index": item.index,
        "username": info.username,
        "caption": info.caption,
        "taken_at": info.taken_at.isoformat() + "Z" if info.taken_at else None,
        "media_type": item.media_type,
        "width": item.width,
        "height": item.height,
        "source_url": f"https://www.instagram.com/p/{info.shortcode}/",
    }


def embed_exif(path: Path, info: PostInfo, item: PostItem) -> None:
    zeroth: dict = {}
    exif_ifd: dict = {}

    if info.username:
        zeroth[piexif.ImageIFD.Artist] = info.username.encode("utf-8")
    if info.caption:
        zeroth[piexif.ImageIFD.ImageDescription] = info.caption.encode("utf-8")
    if info.taken_at:
        stamp = info.taken_at.strftime("%Y:%m:%d %H:%M:%S").encode("ascii")
        zeroth[piexif.ImageIFD.DateTime] = stamp
        exif_ifd[piexif.ExifIFD.DateTimeOriginal] = stamp
        exif_ifd[piexif.ExifIFD.DateTimeDigitized] = stamp

    exif_ifd[piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(
        json.dumps(metadata_payload(info, item), ensure_ascii=False),
        encoding="unicode",
    )

    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif_ifd})
    piexif.insert(exif_bytes, str(path))
