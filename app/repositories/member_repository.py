from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Member, SheetTeam


def create(db: Session, member: Member) -> Member:
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_by_team(db: Session, team_id: int) -> list[Member]:
    stmt = select(Member).where(Member.team_id == team_id).order_by(Member.id)
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, member_id: int) -> Member | None:
    return db.execute(select(Member).where(Member.id == member_id)).scalar_one_or_none()


def get_by_team_and_email(db: Session, team_id: int, email: str) -> Member | None:
    stmt = select(Member).where(Member.team_id == team_id, Member.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_emails_for_sheet(db: Session, sheet_id: int) -> list[str]:
    """시트에 연결된 모든 팀의 멤버 이메일을 반환한다.

    같은 사람이 이 시트를 공유하는 두 팀에 동시에 속해 있으면 행이 두 번 나오므로,
    중복을 제거해야 한 사람이 같은 알림을 두 번 받지 않는다."""
    stmt = (
        select(Member.email)
        .join(SheetTeam, SheetTeam.team_id == Member.team_id)
        .where(SheetTeam.sheet_id == sheet_id)
        .distinct()
        .order_by(Member.email)
    )
    return list(db.execute(stmt).scalars().all())


def delete(db: Session, member: Member) -> None:
    db.delete(member)
    db.commit()
