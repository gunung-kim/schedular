"""라우터 분기. httpx 가 없어 TestClient 대신 라우터 함수를 직접 호출한다."""
import pytest
from fastapi import HTTPException

from app.routers import sheets as sheets_router
from app.routers import team as team_router
from app.schemas.sheet import SheetRegistrationCreate
from app.schemas.team import MemberCreate, TeamCreate
from app.services import sheet_service

from .conftest import at


def _expect(status, fn):
    with pytest.raises(HTTPException) as exc:
        fn()
    assert exc.value.status_code == status
    return exc.value


def test_없는_시트에_발송테스트하면_404(db):
    _expect(404, lambda: sheets_router.send_test_notice(9999, db))


def test_연결된_팀이_없으면_400(db, make_sheet):
    sheet = make_sheet()
    err = _expect(400, lambda: sheets_router.send_test_notice(sheet.id, db))
    assert "팀" in err.detail


def test_시트를_읽지_못하면_502(db, make_sheet, make_team, link, monkeypatch):
    from app.services import google_sheets_client

    sheet = make_sheet()
    link(sheet, make_team("운영팀", ["a@example.com"]))
    monkeypatch.setattr(google_sheets_client, "get_range",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HttpError 403")))
    _expect(502, lambda: sheets_router.send_test_notice(sheet.id, db))


def test_파싱되는_행이_없으면_400(db, make_sheet, make_team, link, sheet_rows):
    sheet = make_sheet()
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows(["제목", "메모"])
    _expect(400, lambda: sheets_router.send_test_notice(sheet.id, db))


def test_메일_발송이_실패하면_502(db, make_sheet, make_team, link, sheet_rows, monkeypatch):
    from app.services import email_client

    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows([at(23, 59).strftime("%H:%M")])
    monkeypatch.setattr(email_client, "send_email",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("SMTP auth failed")))
    _expect(502, lambda: sheets_router.send_test_notice(sheet.id, db))


def test_정상_발송이면_보낸_내용을_그대로_돌려준다(db, make_sheet, make_team, link, sheet_rows, sent):
    sheet = make_sheet(name="근무표", time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com", "b@example.com"]))
    sheet_rows([at(23, 59).strftime("%H:%M")], data="당직 김")

    result = sheets_router.send_test_notice(sheet.id, db)
    assert result.body == "당직 김"
    assert result.recipients == ["a@example.com", "b@example.com"]
    assert result.subject.startswith("[근무표]")
    assert result.row_time.tzinfo is not None
    assert len(sent) == 1


def test_발송테스트는_예약을_건드리지_않는다(scheduler, db, make_sheet, make_team, link, sheet_rows, sent):
    sheet = make_sheet(time_format="%H:%M")
    link(sheet, make_team("운영팀", ["a@example.com"]))
    sheet_rows([at(23, 59).strftime("%H:%M")])
    before = len(scheduler.scheduler.get_jobs())

    sheets_router.send_test_notice(sheet.id, db)
    assert len(scheduler.scheduler.get_jobs()) == before


def test_팀_관련_라우터_오류코드(db, make_team):
    team = make_team("운영팀")
    _expect(400, lambda: team_router.create_team(TeamCreate(name="운영팀"), db))
    _expect(404, lambda: team_router.add_member(9999, MemberCreate(email="a@example.com"), db))
    _expect(404, lambda: team_router.list_members(9999, db))
    _expect(404, lambda: team_router.delete_team(9999, db))
    team_router.add_member(team.id, MemberCreate(email="a@example.com"), db)
    _expect(400, lambda: team_router.add_member(team.id, MemberCreate(email="a@example.com"), db))


def test_시트_팀_연결_라우터_오류코드(db, make_sheet, make_team):
    sheet = make_sheet()
    team = make_team("운영팀")
    assert sheets_router.link_team(sheet.id, team.id, db) == {"ok": True}
    _expect(400, lambda: sheets_router.link_team(sheet.id, team.id, db))
    _expect(404, lambda: sheets_router.link_team(9999, team.id, db))
    _expect(404, lambda: sheets_router.link_team(sheet.id, 9999, db))
    _expect(404, lambda: sheets_router.unlink_team(sheet.id, 9999, db))


@pytest.mark.parametrize("cols,valid", [
    ("B", True), ("B:D", True), ("AA:AC", True),
    ("B:", False), (":D", False), ("B,D", False), ("1", False),
])
def test_열_표기는_등록_단계에서_검증된다(cols, valid):
    """잘못된 값이 저장되면 발송 시각이 돼서야 오류가 드러난다."""
    from pydantic import ValidationError

    payload = dict(name="t", sheet_url="https://docs.google.com/spreadsheets/d/X/edit",
                   time_col="A", data_cols=cols)
    if valid:
        assert SheetRegistrationCreate(**payload).data_cols == cols
    else:
        with pytest.raises(ValidationError):
            SheetRegistrationCreate(**payload)


def test_시트_URL에서_문서ID를_뽑아낸다(db):
    from app.services import google_sheets_client

    url = "https://docs.google.com/spreadsheets/d/1AbCd-_123/edit#gid=0"
    assert google_sheets_client.extract_sheet_id(url) == "1AbCd-_123"
