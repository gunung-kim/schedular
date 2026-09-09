from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import TZ
from app.models import SheetRegistration
from app.repositories import sheet_repository
from app.schemas.sheet import SheetRegistrationCreate
from app.services import google_sheets_client


def create_sheet(db: Session, payload: SheetRegistrationCreate) -> SheetRegistration:
    sheet = SheetRegistration(
        name=payload.name,
        sheet_id=google_sheets_client.extract_sheet_id(payload.sheet_url),
        time_col=payload.time_col,
        data_cols=payload.data_cols,
        header_row=payload.header_row,
        time_format=payload.time_format,
    )
    return sheet_repository.create(db, sheet)


def list_sheets(db: Session) -> list[SheetRegistration]:
    return sheet_repository.get_all(db)


def get_sheet(db: Session, sheet_id: int) -> SheetRegistration | None:
    return sheet_repository.get_by_id(db, sheet_id)


def delete_sheet(db: Session, sheet_id: int) -> bool:
    sheet = get_sheet(db, sheet_id)
    if sheet is None:
        return False
    sheet_repository.delete(db, sheet)
    return True


def _column_range(data_cols: str) -> tuple[str, str]:
    """`data_cols`를 (시작 열, 끝 열)로 해석한다.
    "B:D"는 B~D, "B"처럼 한 열만 적은 경우는 B:B로 본다."""
    start, _, end = data_cols.partition(":")
    start = start.strip()
    return start, (end.strip() or start)


def _parse_time_cells(registration: SheetRegistration) -> list[tuple[int, time]]:
    """`time_col`을 읽어 각 데이터 행의 셀을 (행 번호, 시각) 쌍으로 파싱한다.
    제목행과 `time_format`에 맞지 않는 셀은 건너뛴다."""
    time_values = google_sheets_client.get_range(
        registration.sheet_id, f"{registration.time_col}:{registration.time_col}"
    )

    parsed: list[tuple[int, time]] = []
    for idx, row in enumerate(time_values, start=1):
        if idx < registration.header_row:
            continue
        cell = row[0].strip() if row else ""
        if not cell:
            continue
        try:
            parsed.append((idx, datetime.strptime(cell, registration.time_format).time()))
        except ValueError:
            continue
    return parsed


def find_next_row_time(registration: SheetRegistration, after: datetime | None = None) -> datetime | None:
    """`after`(기본값은 현재 시각)보다 엄격히 뒤에 있는, 가장 가까운 행 시각을 찾아 반환한다.
    `after`가 이미 지난 시각이면 현재 시각을 기준으로 삼아 지나간 행은 건너뛴다.
    오늘 남은 행이 하나도 없으면 내일 가장 이른 행으로 넘어간다.
    파싱 가능한 시간 행이 아예 없으면 None을 반환한다.
    반환값은 TIMEZONE이 적용된 aware datetime이다."""
    # `after`(직전에 처리한 행 시각)가 이미 지났으면 현재 시각을 기준으로 삼는다.
    # 잠자기 등으로 밀렸을 때 지나간 행들을 건너뛰기 위한 것 -
    # 11시간 전 알림을 지금 보내는 건 의미가 없고, 밀린 만큼 한꺼번에 쏟아지지도 않는다.
    now = datetime.now(TZ)
    reference = max(after, now) if after else now
    times = _parse_time_cells(registration)
    if not times:
        return None

    today = reference.date()
    upcoming_today = [dt for _, t in times if (dt := datetime.combine(today, t, tzinfo=TZ)) > reference]
    if upcoming_today:
        return min(upcoming_today)

    tomorrow = today + timedelta(days=1)
    return min(datetime.combine(tomorrow, t, tzinfo=TZ) for _, t in times)


def get_row_data_at(registration: SheetRegistration, target_dt: datetime) -> list[str] | None:
    """시트를 다시 읽어, 시각이 `target_dt`와 일치하는 행의 `data_cols` 값들을 반환한다."""
    # 시트에 적힌 시각은 타임존 없는 벽시계 시각이므로,
    # target_dt에서도 .time()으로 tzinfo를 떼어내고 벽시계 기준으로 비교한다.
    matched_row = next(
        (idx for idx, t in _parse_time_cells(registration) if t == target_dt.time()),
        None,
    )
    if matched_row is None:
        return None

    start_col, end_col = _column_range(registration.data_cols)
    data_values = google_sheets_client.get_range(
        registration.sheet_id, f"{start_col}{matched_row}:{end_col}{matched_row}"
    )
    return data_values[0] if data_values else None
