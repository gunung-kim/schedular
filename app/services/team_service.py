from sqlalchemy.orm import Session

from app.models import Member, Team
from app.repositories import member_repository, team_repository
from app.schemas.team import MemberCreate, TeamCreate


def create_team(db: Session, payload: TeamCreate) -> Team | None:
    """팀을 만든다. 같은 이름이 이미 있으면 None."""
    if team_repository.get_by_name(db, payload.name) is not None:
        return None
    return team_repository.create(db, Team(name=payload.name))


def list_teams(db: Session) -> list[Team]:
    return team_repository.get_all(db)


def get_team(db: Session, team_id: int) -> Team | None:
    return team_repository.get_by_id(db, team_id)


def delete_team(db: Session, team_id: int) -> bool:
    """팀과 그 멤버를 지운다. 시트는 공용일 수 있으므로 연결만 끊기고 시트 자체는 남는다
    (멤버·연결 삭제는 외래키 CASCADE 가 처리한다)."""
    team = team_repository.get_by_id(db, team_id)
    if team is None:
        return False
    team_repository.delete(db, team)
    return True


def add_member(db: Session, team_id: int, payload: MemberCreate) -> Member | None:
    """팀에 수신자를 추가한다. 같은 팀에 이미 있는 이메일이면 None."""
    if member_repository.get_by_team_and_email(db, team_id, payload.email) is not None:
        return None
    return member_repository.create(db, Member(team_id=team_id, email=payload.email))


def list_members(db: Session, team_id: int) -> list[Member]:
    return member_repository.get_by_team(db, team_id)


def delete_member(db: Session, member_id: int) -> bool:
    member = member_repository.get_by_id(db, member_id)
    if member is None:
        return False
    member_repository.delete(db, member)
    return True
