"""Validate pickup codes and atomically collect their parcels."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock, as_utc
from ..errors import CodeExpired, CodeUsed, DomainError, NoSuchCode
from ..models import Door, Parcel
from ..settings import Settings
from .codes import hash_code, matches


def find_parcel(session: Session, hashed_code: str) -> Parcel | None:
    return session.scalar(
        select(Parcel).where(Parcel.code_hash == hashed_code).limit(1)
    )


def pickup(session: Session, code: str, clock: Clock, settings: Settings) -> tuple[Parcel, Door]:
    key = settings.code_hash_key
    parcel = find_parcel(session, hash_code(key, code))
    if parcel is None or not matches(key, code, parcel.code_hash):
        raise NoSuchCode()

    now = as_utc(clock.now())
    if parcel.code_used_at is not None:
        raise CodeUsed("This code has already opened its door")
    if now > as_utc(parcel.code_expires_at):
        raise CodeExpired("That code's window has passed")

    door = session.scalar(
        select(Door).where(Door.current_parcel_id == parcel.id)
    )
    if door is None:
        raise DomainError("This code is valid, but its door is not holding the parcel")

    dwell_seconds = int((now - as_utc(parcel.dropped_at)).total_seconds())
    try:
        parcel.code_used_at = now
        parcel.state = "collected"
        parcel.collected_at = now
        parcel.dwell_seconds = dwell_seconds
        session.flush()
        door.current_parcel_id = None
        session.commit()
    except Exception:
        session.rollback()
        raise

    return parcel, door
