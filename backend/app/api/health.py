from fastapi import APIRouter

from .. import __version__

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
