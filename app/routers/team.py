from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.team import TeamMemberCreate, TeamMemberOut
from app.services import team_service

router = APIRouter(prefix="/team", tags=["team"])


@router.post("", response_model=TeamMemberOut)
def create_member(payload: TeamMemberCreate, db: Session = Depends(get_db)):
    member = team_service.create_member(db, payload)
    if member is None:
        raise HTTPException(status_code=400, detail="Email already registered")
    return member


@router.get("", response_model=list[TeamMemberOut])
def list_members(db: Session = Depends(get_db)):
    return team_service.list_members(db)


@router.delete("/{member_id}")
def delete_member(member_id: int, db: Session = Depends(get_db)):
    if not team_service.delete_member(db, member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}
