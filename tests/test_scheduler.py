"""체인이 끊기지 않는지, 밀린 알림을 어떻게 처리하는지.

이 파일이 지키는 것들은 전부 실제로 한 번씩 터졌던 문제다:
운영 중 체인이 조용히 멈추거나, 잠자기에서 깨어나며 밀린 알림이 쏟아지거나,
감시 job 이 정상 상태를 고장으로 오해하는 경우.
"""
from datetime import datetime, timedelta

from app.config import NOTICE_LEAD_MINUTES, TZ
from app.repositories import sheet_repository
from app.services import sheet_service


def _job(module, sheet):
    return module.scheduler.get_job(module._job_id(sheet.id))


def _rows_at(*offsets_hours: float) -> list[str]:
    """지금부터 N시간 뒤 시각들을 시트 표기로 만든다."""
    now = datetime.now(TZ)
    return [(now + timedelta(hours=h)).strftime("%H:%M") for h in offsets_hours]


def test_기동하면_시트마다_예약되고_감시job도_등록된다(stopped_scheduler, make_sheet, sheet_rows, make_team, link):
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(2))

    stopped_scheduler.start_scheduler()
    assert _job(stopped_scheduler, sheet) is not None
    assert stopped_scheduler.scheduler.get_job(stopped_scheduler._WATCHDOG_JOB_ID) is not None


def test_예약은_행_시각보다_NOTICE_LEAD_MINUTES_앞선다(scheduler, make_sheet, sheet_rows, make_team, link):
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(3))

    scheduler.schedule_sheet(sheet.id)
    expected = sheet_service.find_next_row_time(sheet) - timedelta(minutes=NOTICE_LEAD_MINUTES)
    assert _job(scheduler, sheet).trigger.run_date == expected


def test_시트를_읽지_못하면_재시도가_예약된다(scheduler, make_sheet, monkeypatch):
    """예외를 밖으로 던지면 그 시트는 재시작 전까지 영영 멈춘다."""
    from app.services import google_sheets_client

    sheet = make_sheet()
    monkeypatch.setattr(google_sheets_client, "get_range",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HttpError 503")))
    scheduler.schedule_sheet(sheet.id)
    assert _job(scheduler, sheet).func is scheduler._reschedule


def test_파싱되는_행이_없어도_재시도가_예약된다(scheduler, make_sheet, sheet_rows):
    """시트가 잠시 비어 있을 뿐일 수 있으므로 포기하지 않는다."""
    sheet = make_sheet()
    sheet_rows(["제목", "메모"])
    scheduler.schedule_sheet(sheet.id)
    assert _job(scheduler, sheet).func is scheduler._reschedule


def test_예약_중_DB오류가_나도_체인은_살아남는다(scheduler, make_sheet, monkeypatch):
    sheet = make_sheet()
    monkeypatch.setattr(sheet_repository, "get_by_id",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("DB gone")))
    scheduler._reschedule(sheet.id)
    assert _job(scheduler, sheet) is not None


def test_발송에_실패해도_다음_알림은_예약된다(scheduler, make_sheet, sheet_rows, make_team, link, monkeypatch):
    from app.services import email_client

    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(2, 3))
    monkeypatch.setattr(email_client, "send_email",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("SMTP down")))

    scheduler._fire(sheet.id, sheet_service.find_next_row_time(sheet))
    assert _job(scheduler, sheet) is not None


def test_시트가_삭제되었으면_체인을_끝낸다(scheduler, db, make_sheet):
    sheet = make_sheet()
    sheet_id = sheet.id
    sheet_repository.delete(db, sheet)
    scheduler._fire(sheet_id, datetime.now(TZ))
    assert scheduler.scheduler.get_job(scheduler._job_id(sheet_id)) is None


def test_너무_늦은_알림은_보내지_않고_체인만_이어간다(scheduler, make_sheet, sheet_rows, make_team, link, sent):
    """잠자기에서 깨어나 11시간 지난 알림을 지금 보내는 것은 의미가 없다."""
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(1, 2))

    stale = datetime.now(TZ) - timedelta(hours=11)
    scheduler._fire(sheet.id, stale)
    assert sent == []
    assert _job(scheduler, sheet) is not None


def test_조금_늦은_알림은_그대로_보낸다(scheduler, make_sheet, sheet_rows, make_team, link, sent):
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    # 유예 안쪽으로 조금 지난 행이 시트에 실제로 있어야 한다
    late_target = (datetime.now(TZ) - timedelta(minutes=NOTICE_LEAD_MINUTES - 5)).replace(second=0, microsecond=0)
    sheet_rows([late_target.strftime("%H:%M")])

    scheduler._fire(sheet.id, late_target)
    assert len(sent) == 1


def test_연결된_팀이_없으면_시트를_읽지도_않는다(scheduler, make_sheet, sheet_rows, sent):
    """수신자 0명이면 구글 API 를 호출할 이유가 없다. 남는 1회는 다음 행 예약용."""
    sheet = make_sheet(time_format="%H:%M")
    calls = sheet_rows(_rows_at(1, 2))

    target = sheet_service.find_next_row_time(sheet)
    calls.clear()                       # 여기서부터가 _fire 가 쓰는 호출
    scheduler._fire(sheet.id, target)
    assert sent == []
    assert len(calls) == 1              # 발송용 2회는 생략, 다음 행 예약용 1회만
    assert _job(scheduler, sheet) is not None


def test_팀을_연결하면_재시작_없이_발송이_재개된다(scheduler, db, make_sheet, sheet_rows, make_team, link, sent):
    sheet = make_sheet(time_format="%H:%M")
    sheet_rows(_rows_at(1, 2))
    target = sheet_service.find_next_row_time(sheet)

    scheduler._fire(sheet.id, target)
    assert sent == []

    link(sheet, make_team("운영팀", ["a@example.com"]))
    scheduler._fire(sheet.id, target)
    assert len(sent) == 1
    assert sent[0]["recipients"] == ["a@example.com"]


def test_감시job은_예약이_멀쩡하면_아무것도_하지_않는다(scheduler, make_sheet, sheet_rows, make_team, link):
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(2))
    scheduler.schedule_sheet(sheet.id)
    before = _job(scheduler, sheet).trigger.run_date

    for _ in range(5):
        scheduler._watchdog()
    assert _job(scheduler, sheet).trigger.run_date == before


def test_감시job은_사라진_예약을_복구한다(scheduler, make_sheet, sheet_rows, make_team, link):
    """APScheduler 는 같은 id 의 job 이 실행 중이면 새 job 을 예외 없이 버린다.
    조용히 사라지는 경우라 예외 기반 재시도로는 잡히지 않는다."""
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(2))
    scheduler.schedule_sheet(sheet.id)

    scheduler.scheduler.remove_job(scheduler._job_id(sheet.id))
    assert _job(scheduler, sheet) is None
    scheduler._watchdog()
    assert _job(scheduler, sheet) is not None


def test_감시job은_처리중인_시트를_건드리지_않는다(scheduler, make_sheet, sheet_rows, make_team, link):
    """_fire 실행 중에는 그 시트의 job 이 잠시 없다.
    이때 감시가 고장으로 오해하고 재예약하면 같은 알림이 두 번 나간다."""
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(_rows_at(2))

    scheduler._in_flight.add(sheet.id)
    try:
        scheduler._watchdog()
        assert _job(scheduler, sheet) is None
    finally:
        scheduler._in_flight.discard(sheet.id)
