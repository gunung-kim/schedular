from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.scheduler import schedule_sheet, unschedule_sheet
from app.schemas.sheet import SheetRegistrationCreate, SheetRegistrationOut, SheetTestResult
from app.services import notification_service, sheet_service, team_service

router = APIRouter(prefix="/sheets", tags=["sheets"])


@router.post("", response_model=SheetRegistrationOut)
def create_sheet(payload: SheetRegistrationCreate, db: Session = Depends(get_db)):
    sheet = sheet_service.create_sheet(db, payload)
    schedule_sheet(sheet.id)
    return sheet


@router.get("", response_model=list[SheetRegistrationOut])
def list_sheets(db: Session = Depends(get_db)):
    return sheet_service.list_sheets(db)


@router.post("/{sheet_id}/test", response_model=SheetTestResult)
def send_test_notice(sheet_id: int, db: Session = Depends(get_db)):
    """다음 행 기준으로 메일을 한 통 실제 발송해 설정을 점검한다.
    예약된 일정은 건드리지 않으므로, 정규 발송은 원래대로 진행된다."""
    sheet = sheet_service.get_sheet(db, sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Sheet not found")

    if not team_service.list_members(db):
        raise HTTPException(status_code=400, detail="등록된 팀원이 없습니다. POST /team 으로 먼저 등록하세요.")

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
