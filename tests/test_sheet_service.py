"""시각 파싱과 '다음 행 찾기' 로직."""
from datetime import datetime, timedelta

import pytest

from app.config import TZ
from app.services import sheet_service

from .conftest import at


def test_다음_행은_기준시각_이후_가장_가까운_것(make_sheet, sheet_rows):
    sheet = make_sheet()
    sheet_rows(["9:00", "13:00", "18:00"])
    assert sheet_service.find_next_row_time(sheet, after=at(12, 53)) == at(13)


def test_오늘_행이_다_지나면_내일_첫_행으로_넘어간다(make_sheet, sheet_rows):
    sheet = make_sheet()
    sheet_rows(["9:00", "13:00", "18:00"])
    from .conftest import FUTURE_DAYS

    assert sheet_service.find_next_row_time(sheet, after=at(20)) == at(9, days=FUTURE_DAYS + 1)


def test_반환값은_설정된_타임존의_aware_datetime(make_sheet, sheet_rows):
    """서버 OS 가 UTC 여도 시트의 '9:00' 은 KST 09:00 으로 해석되어야 한다."""
    sheet = make_sheet()
    sheet_rows(["9:00"])
    result = sheet_service.find_next_row_time(sheet, after=at(1))
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(hours=9)


def test_지나간_행은_건너뛴다(make_sheet, sheet_rows):
    """잠자기 등으로 after 가 한참 과거면 현재 시각이 기준이 된다.
    밀린 알림이 한꺼번에 쏟아지지 않게 하는 핵심 동작."""
    sheet = make_sheet()
    sheet_rows([f"{h}:00" for h in range(1, 23)])
    now = datetime.now(TZ)
    result = sheet_service.find_next_row_time(sheet, after=now - timedelta(hours=11))
    assert result > now


def test_time_format_에_맞지_않는_행은_무시된다(make_sheet, sheet_rows):
    sheet = make_sheet(time_format="%H:%M")
    sheet_rows(["제목", "9:00", "메모", "13:00"])
    assert sheet_service.find_next_row_time(sheet, after=at(0)) == at(9)


def test_파싱되는_행이_없으면_None(make_sheet, sheet_rows):
    sheet = make_sheet()
    sheet_rows(["제목", "메모"])
    assert sheet_service.find_next_row_time(sheet, after=at(0)) is None


@pytest.mark.parametrize("data_cols,expected", [("B", "B"), ("B:D", "B")])
def test_한_열만_적어도_동작한다(data_cols, expected):
    """'B' 는 'B:B' 로 해석된다. 콜론 없이 등록된 기존 데이터를 살리기 위한 처리."""
    start, end = sheet_service._column_range(data_cols)
    assert start == expected
