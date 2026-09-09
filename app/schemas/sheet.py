from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SheetRegistrationCreate(BaseModel):
    name: str
    sheet_url: str
    # 열 표기는 A~ZZZ 형태만 허용한다. 잘못된 값이 저장되면 발송 시점에야 오류가 드러나므로
    # 등록 단계에서 걸러낸다.
    time_col: str = Field(pattern=r"^[A-Za-z]{1,3}$")
    data_cols: str = Field(pattern=r"^[A-Za-z]{1,3}(:[A-Za-z]{1,3})?$")
    header_row: int = Field(default=1, ge=1)
    time_format: str = "%H시"


class SheetRegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sheet_id: str
    time_col: str
    data_cols: str
    header_row: int
    time_format: str
    created_at: datetime


class SheetTestResult(BaseModel):
    """발송 테스트 결과. 어떤 행이 어떤 내용으로 누구에게 나갔는지 그대로 돌려준다."""

    row_time: datetime
    subject: str
    body: str
    recipients: list[str]
