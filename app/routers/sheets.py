from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import member_repository
from app.scheduler import schedule_sheet, unschedule_sheet
from app.schemas.sheet import SheetRegistrationCreate, SheetRegistrationOut, SheetTestResult
from app.schemas.team import TeamOut
from app.services import notification_service, sheet_service

router = APIRouter(prefix="/sheets", tags=["sheets"])


@router.post("", response_model=SheetRegistrationOut)
def create_sheet(payload: SheetRegistrationCreate, db: Session = Depends(get_db)):
    sheet = sheet_service.create_sheet(db, payload)
    schedule_sheet(sheet.id)
    return sheet


@router.get("", response_model=list[SheetRegistrationOut])
def list_sheets(team_id: int | None = None, db: Session = Depends(get_db)):
    """team_id 를 주면 그 팀에 연결된 시트만 반환한다."""
    return sheet_service.list_sheets(db, team_id=team_id)


@router.get("/{sheet_id}/teams", response_model=list[TeamOut])
def list_sheet_teams(sheet_id: int, db: Session = Depends(get_db)):
    """이 시트를 공유하는 팀 목록. 여기 속한 멤버가 알림 수신자가 된다."""
    if sheet_service.get_sheet(db, sheet_id) is None:
        raise HTTPException(status_code=404, detail="Sheet not found")
    return sheet_service.list_teams(db, sheet_id)


@router.post("/{sheet_id}/teams/{team_id}")
def link_team(sheet_id: int, team_id: int, db: Session = Depends(get_db)):
    """시트를 팀에 연결한다. 연결된 순간부터 그 팀 멤버가 알림을 받는다."""
    result = sheet_service.link_team(db, sheet_id, team_id)
    if result == "no_sheet":
        raise HTTPException(status_code=404, detail="Sheet not found")
    if result == "no_team":
        raise HTTPException(status_code=404, detail="Team not found")
    if result == "already":
        raise HTTPException(status_code=400, detail="이미 연결된 팀입니다.")
    return {"ok": True}


@router.delete("/{sheet_id}/teams/{team_id}")
def unlink_team(sheet_id: int, team_id: int, db: Session = Depends(get_db)):
    if not sheet_service.unlink_team(db, sheet_id, team_id):
        raise HTTPException(status_code=404, detail="연결되어 있지 않습니다.")
    return {"ok": True}


@router.post("/{sheet_id}/test", response_model=SheetTestResult)
def send_test_notice(sheet_id: int, db: Session = Depends(get_db)):
    """다음 행 기준으로 메일을 한 통 실제 발송해 설정을 점검한다.
    예약된 일정은 건드리지 않으므로, 정규 발송은 원래대로 진행된다."""
    sheet = sheet_service.get_sheet(db, sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Sheet not found")

    if not member_repository.get_emails_for_sheet(db, sheet_id):
        raise HTTPException(
            status_code=400,
            detail="이 시트의 수신자가 없습니다. 시트에 팀을 연결하고(POST /sheets/{id}/teams/{team_id}) "
                   "그 팀에 멤버를 추가하세요.",
        )

    try:
        target_dt = sheet_service.find_next_row_time(sheet)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"시트를 읽지 못했습니다: {exc}") from exc

    if target_dt is None:
        raise HTTPException(
            status_code=400,
            detail="시트에서 파싱 가능한 시간 행을 찾지 못했습니다. time_col / time_format / header_row 설정을 확인하세요.",
        )

    try:
        result = notification_service.send_row_notice(db, sheet, target_dt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"메일 발송에 실패했습니다: {exc}") from exc

    if result is None:
        raise HTTPException(status_code=400, detail=f"{target_dt} 에 해당하는 행을 찾지 못했습니다.")

    return SheetTestResult(row_time=target_dt, subject=result.subject,
                           body=result.body, recipients=result.recipients)


@router.delete("/{sheet_id}")
def delete_sheet(sheet_id: int, db: Session = Depends(get_db)):
    if not sheet_service.delete_sheet(db, sheet_id):
        raise HTTPException(status_code=404, detail="Sheet not found")
    unschedule_sheet(sheet_id)
    return {"ok": True}
