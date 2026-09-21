"""테스트 공통 설정.

app 모듈을 import 하기 전에 DATABASE_URL 을 임시 파일로 돌려놓는다.
app/database.py 가 import 시점에 엔진을 만들기 때문에 순서가 중요하다.
"""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")

from datetime import datetime, timedelta  # noqa: E402

import pytest  # noqa: E402

from app.config import TZ  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Member, SheetRegistration, SheetTeam, Team  # noqa: E402
import smtplib  # noqa: E402

from app.services import email_client, google_sheets_client  # noqa: E402

Base.metadata.create_all(bind=engine)

FUTURE_DAYS = 10   # at() 기본 오프셋


@pytest.fixture
def db():
    """테스트마다 빈 DB 로 시작한다."""
    session = SessionLocal()
    for model in (SheetTeam, Member, SheetRegistration, Team):
        session.query(model).delete()
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """어떤 테스트도 실제 구글 API 나 SMTP 를 건드리지 못하게 막는다.
    스텁을 갈아끼우지 않은 테스트가 네트워크로 나가면 그 자리에서 실패한다."""
    def blocked(*args, **kwargs):
        raise AssertionError("테스트가 실제 네트워크를 호출하려 했습니다. 스텁을 사용하세요.")

    monkeypatch.setattr(google_sheets_client, "get_range", blocked)
    # send_email 자체가 아니라 그 아래 SMTP 소켓을 막는다.
    # email_client 의 동작(헤더 구성 등)은 실제 코드로 검증해야 하기 때문.
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)


@pytest.fixture
def sheet_rows(monkeypatch):
    """시트 내용을 지정하는 스텁을 설치하고, 호출된 range 목록을 돌려준다.

    사용: calls = sheet_rows(["9:00", "13:00"], data="당직 김")
    """
    def install(times: list[str], data: str = "데이터") -> list[str]:
        calls: list[str] = []

        def fake_get_range(sheet_id: str, cell_range: str):
            calls.append(cell_range)
            if cell_range.startswith(("A", "'")) and ":" in cell_range and cell_range[1] == ":":
                return [[t] for t in times]
            return [[data]]

        monkeypatch.setattr(google_sheets_client, "get_range", fake_get_range)
        return calls

    return install


@pytest.fixture
def sent(monkeypatch):
    """발송된 메일을 모으는 스텁. 실제 SMTP 는 타지 않는다."""
    box: list[dict] = []
    monkeypatch.setattr(email_client, "send_email", lambda **kw: box.append(kw))
    return box


@pytest.fixture
def make_sheet(db):
    def _make(name="근무표", time_format="%H:%M", data_cols="B", header_row=1):
        sheet = SheetRegistration(
            name=name, sheet_id="SHEET_ID", time_col="A",
            data_cols=data_cols, header_row=header_row, time_format=time_format,
        )
        db.add(sheet)
        db.commit()
        db.refresh(sheet)
        return sheet
    return _make


@pytest.fixture
def make_team(db):
    def _make(name="운영팀", emails=()):
        team = Team(name=name)
        db.add(team)
        db.flush()
        for email in emails:
            db.add(Member(team_id=team.id, email=email))
        db.commit()
        db.refresh(team)
        return team
    return _make


@pytest.fixture
def link(db):
    def _link(sheet, team):
        db.add(SheetTeam(sheet_id=sheet.id, team_id=team.id))
        db.commit()
    return _link


@pytest.fixture
def stopped_scheduler():
    """start_scheduler() 자체를 검증할 때 쓰는, 아직 기동하지 않은 스케줄러."""
    from app import scheduler as module

    module._in_flight.clear()
    try:
        yield module
    finally:
        module.scheduler.remove_all_jobs()
        if module.scheduler.running:
            module.scheduler.shutdown(wait=False)


@pytest.fixture
def scheduler():
    """멈춰 있는(paused) 스케줄러. 실제 jobstore 를 쓰되 job 이 실행되지는 않는다.
    시작하지 않은 스케줄러는 job 이 pending 으로만 쌓여 replace_existing 이 동작하지 않으므로
    반드시 start(paused=True) 로 띄운다."""
    from app import scheduler as module

    module.scheduler.start(paused=True)
    module._in_flight.clear()
    try:
        yield module
    finally:
        module.scheduler.remove_all_jobs()
        module.scheduler.shutdown(wait=False)


def at(hour: int, minute: int = 0, days: int = FUTURE_DAYS) -> datetime:
    """특정 시각의 aware datetime. 기본적으로 충분히 미래의 날짜를 쓴다.

    find_next_row_time 은 `max(after, now)` 로 지나간 행을 건너뛰므로,
    `after` 가 과거면 결과가 실행 시각에 따라 달라진다.
    시각 계산 자체를 검증할 때는 미래 날짜를 써서 테스트를 결정적으로 만든다."""
    now = datetime.now(TZ)
    return (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
