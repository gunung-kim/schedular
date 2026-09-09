from sqlalchemy.orm import Session

from app.models import TeamMember
from app.repositories import team_repository
from app.schemas.team import TeamMemberCreate


def create_member(db: Session, payload: TeamMemberCreate) -> TeamMember | None:
    if team_repository.get_by_email(db, payload.email) is not None:
        return None
    member = TeamMember(email=payload.email)
    return team_repository.create(db, member)


def list_members(db: Session) -> list[TeamMember]:
    return team_repository.get_all(db)


def delete_member(db: Session, member_id: int) -> bool:
    member = team_repository.get_by_id(db, member_id)
    if member is None:
        return False
    team_repository.delete(db, member)
    return True
