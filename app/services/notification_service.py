from datetime import datetime
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models import SheetRegistration
from app.repositories import team_repository
from app.services import email_client, sheet_service


class NoticeResult(NamedTuple):
    """발송한 내용. 로그와 API 응답에서 그대로 쓴다."""
    subject: str
    body: str
    recipients: list[str]


def build_subject(registration: SheetRegistration, target_dt: datetime) -> str:
    return f"[{registration.name}] {target_dt.strftime(registration.time_format)} 알림"


def send_row_notice(db: Session, registration: SheetRegistration, target_dt: datetime) -> NoticeResult | None:
    """`target_dt`에 해당하는 행을 시트에서 읽어 팀원 전원에게 발송한다.

    예약 발송과 발송 테스트가 똑같은 경로를 타도록 여기 한 곳에 모아둔다.
    일치하는 행이 없으면 아무것도 보내지 않고 None을 반환한다."""
    data = sheet_service.get_row_data_at(registration, target_dt)
    if data is None:
        return None

    result = NoticeResult(
        subject=build_subject(registration, target_dt),
        body="\n".join(data),
        recipients=[m.email for m in team_repository.get_all(db)],
    )
    email_client.send_email(subject=result.subject, body=result.body, recipients=result.recipients)
    return result
