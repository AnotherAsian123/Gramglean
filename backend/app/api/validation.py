import re

from fastapi import HTTPException

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def normalize_username(raw: str) -> str:
    """Validate and normalise an Instagram handle. Rejects anything that isn't a
    plain handle so it can never be smuggled into a path or subprocess arg."""
    if not raw:
        raise HTTPException(status_code=400, detail="Username is required.")
    name = raw.strip().lstrip("@").strip("/").lower()
    # Tolerate a pasted profile URL.
    if "instagram.com" in name:
        name = name.split("instagram.com/", 1)[-1].split("/", 1)[0]
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid Instagram username: {raw!r}")
    return name
