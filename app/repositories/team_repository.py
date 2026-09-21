from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Team


def create(db: Session, team: Team) -> Team:
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_all(db: Session) -> list[Team]:
    return list(db.execute(select(Team).order_by(Team.id)).scalars().all())


def get_by_id(db: Session, team_id: int) -> Team | None:
    return db.execute(select(Team).where(Team.id == team_id)).scalar_one_or_none()


def get_by_name(db: Session, name: str) -> Team | None:
    return db.execute(select(Team).where(Team.name == name)).scalar_one_or_none()


def delete(db: Session, team: Team) -> None:
    db.delete(team)
    db.commit()
