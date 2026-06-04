from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db.database import get_session
from ..db.models import Account, Job, Media
from .validation import normalize_username

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    username: str
    include_posts: bool = True
    include_reels: bool = True
    include_stories: bool = False


class AccountUpdate(BaseModel):
    include_posts: Optional[bool] = None
    include_reels: Optional[bool] = None
    include_stories: Optional[bool] = None


@router.get("")
def list_accounts(session: Session = Depends(get_session)) -> List[dict]:
    accounts = session.exec(select(Account).order_by(Account.username)).all()
    out = []
    for acc in accounts:
        media_count = session.exec(
            select(Media).where(Media.account_id == acc.id)
        ).all()
        data = acc.model_dump()
        data["media_count"] = len(media_count)
        out.append(data)
    return out


@router.post("", status_code=201)
def create_account(payload: AccountCreate, session: Session = Depends(get_session)) -> Account:
    username = normalize_username(payload.username)
    existing = session.exec(select(Account).where(Account.username == username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already on the watchlist.")
    account = Account(
        username=username,
        include_posts=payload.include_posts,
        include_reels=payload.include_reels,
        include_stories=payload.include_stories,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.patch("/{account_id}")
def update_account(
    account_id: int, payload: AccountUpdate, session: Session = Depends(get_session)
) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(account, field, value)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, session: Session = Depends(get_session)) -> None:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    # Remove DB rows only; downloaded files on disk are left untouched.
    for media in session.exec(select(Media).where(Media.account_id == account_id)).all():
        session.delete(media)
    for job in session.exec(select(Job).where(Job.account_id == account_id)).all():
        session.delete(job)
    session.delete(account)
    session.commit()
