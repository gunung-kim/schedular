from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TeamMember


def create(db: Session, member: TeamMember) -> TeamMember:
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_all(db: Session) -> list[TeamMember]:
    return list(db.execute(select(TeamMember)).scalars().all())


def get_by_id(db: Session, member_id: int) -> TeamMember | None:
    stmt = select(TeamMember).where(TeamMember.id == member_id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_email(db: Session, email: str) -> TeamMember | None:
    stmt = select(TeamMember).where(TeamMember.email == email)
    return db.execute(stmt).scalar_one_or_none()


def delete(db: Session, member: TeamMember) -> None:
    db.delete(member)
    db.commit()
