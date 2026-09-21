from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.team import MemberCreate, MemberOut, TeamCreate, TeamOut
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamOut)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    team = team_service.create_team(db, payload)
    if team is None:
        raise HTTPException(status_code=400, detail="이미 같은 이름의 팀이 있습니다.")
    return team


@router.get("", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return team_service.list_teams(db)


@router.delete("/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    """팀과 소속 멤버를 지운다. 시트는 다른 팀이 함께 쓸 수 있으므로 연결만 끊기고 남는다."""
    if not team_service.delete_team(db, team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return {"ok": True}


@router.post("/{team_id}/members", response_model=MemberOut)
def add_member(team_id: int, payload: MemberCreate, db: Session = Depends(get_db)):
    if team_service.get_team(db, team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    member = team_service.add_member(db, team_id, payload)
    if member is None:
        raise HTTPException(status_code=400, detail="이 팀에 이미 등록된 이메일입니다.")
    return member


@router.get("/{team_id}/members", response_model=list[MemberOut])
def list_members(team_id: int, db: Session = Depends(get_db)):
    if team_service.get_team(db, team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_service.list_members(db, team_id)


@router.delete("/{team_id}/members/{member_id}")
def delete_member(team_id: int, member_id: int, db: Session = Depends(get_db)):
    if not team_service.delete_member(db, member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}
