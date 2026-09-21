from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SheetRegistration, SheetTeam, Team


def create(db: Session, sheet: SheetRegistration) -> SheetRegistration:
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet


def get_all(db: Session, team_id: int | None = None) -> list[SheetRegistration]:
    stmt = select(SheetRegistration)
    if team_id is not None:
        stmt = stmt.join(SheetTeam, SheetTeam.sheet_id == SheetRegistration.id).where(
            SheetTeam.team_id == team_id
        )
    return list(db.execute(stmt.order_by(SheetRegistration.id)).scalars().all())


def get_by_id(db: Session, sheet_id: int) -> SheetRegistration | None:
    stmt = select(SheetRegistration).where(SheetRegistration.id == sheet_id)
    return db.execute(stmt).scalar_one_or_none()


def delete(db: Session, sheet: SheetRegistration) -> None:
    db.delete(sheet)
    db.commit()


def get_teams(db: Session, sheet_id: int) -> list[Team]:
    stmt = (
        select(Team)
        .join(SheetTeam, SheetTeam.team_id == Team.id)
        .where(SheetTeam.sheet_id == sheet_id)
        .order_by(Team.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_link(db: Session, sheet_id: int, team_id: int) -> SheetTeam | None:
    stmt = select(SheetTeam).where(SheetTeam.sheet_id == sheet_id, SheetTeam.team_id == team_id)
    return db.execute(stmt).scalar_one_or_none()


def link_team(db: Session, sheet_id: int, team_id: int) -> SheetTeam:
    link = SheetTeam(sheet_id=sheet_id, team_id=team_id)
    db.add(link)
    db.commit()
    return link


def unlink_team(db: Session, link: SheetTeam) -> None:
    db.delete(link)
    db.commit()
