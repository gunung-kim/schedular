"""팀·멤버·시트 연결과 수신자 라우팅."""
from app.models import Member, SheetRegistration, SheetTeam
from app.repositories import member_repository
from app.schemas.team import MemberCreate, TeamCreate
from app.services import sheet_service, team_service


def test_같은_이름의_팀은_만들_수_없다(db):
    assert team_service.create_team(db, TeamCreate(name="운영팀")) is not None
    assert team_service.create_team(db, TeamCreate(name="운영팀")) is None


def test_같은_사람이_여러_팀에_속할_수_있다(db, make_team):
    a = make_team("A팀", ["charlie@example.com"])
    b = make_team("B팀", ["charlie@example.com"])
    assert len(member_repository.get_by_team(db, a.id)) == 1
    assert len(member_repository.get_by_team(db, b.id)) == 1


def test_같은_팀_안에서는_이메일이_중복될_수_없다(db, make_team):
    team = make_team("운영팀", ["alice@example.com"])
    assert team_service.add_member(db, team.id, MemberCreate(email="alice@example.com")) is None


def test_수신자는_연결된_팀의_멤버뿐이다(db, make_sheet, make_team, link):
    sheet = make_sheet()
    a = make_team("A팀", ["alice@example.com"])
    make_team("B팀", ["bob@example.com"])          # 연결하지 않은 팀
    link(sheet, a)
    assert member_repository.get_emails_for_sheet(db, sheet.id) == ["alice@example.com"]


def test_공용_시트는_연결된_모든_팀이_받는다(db, make_sheet, make_team, link):
    sheet = make_sheet()
    a = make_team("A팀", ["alice@example.com"])
    b = make_team("B팀", ["bob@example.com"])
    link(sheet, a)
    link(sheet, b)
    assert member_repository.get_emails_for_sheet(db, sheet.id) == ["alice@example.com", "bob@example.com"]


def test_두_팀에_속한_사람도_한_번만_받는다(db, make_sheet, make_team, link):
    """중간 테이블 조인이라 중복 제거가 없으면 같은 알림을 두 통 받게 된다."""
    sheet = make_sheet()
    a = make_team("A팀", ["alice@example.com", "charlie@example.com"])
    b = make_team("B팀", ["bob@example.com", "charlie@example.com"])
    link(sheet, a)
    link(sheet, b)
    emails = member_repository.get_emails_for_sheet(db, sheet.id)
    assert emails.count("charlie@example.com") == 1
    assert emails == ["alice@example.com", "bob@example.com", "charlie@example.com"]


def test_연결되지_않은_시트는_수신자가_없다(db, make_sheet, make_team):
    sheet = make_sheet()
    make_team("운영팀", ["alice@example.com"])
    assert member_repository.get_emails_for_sheet(db, sheet.id) == []


def test_팀을_지우면_멤버와_연결은_사라지고_시트는_남는다(db, make_sheet, make_team, link):
    """시트는 다른 팀이 공유할 수 있으므로 함께 지우지 않는다.
    CASCADE 는 SQLite 의 PRAGMA foreign_keys 가 켜져 있어야 동작한다."""
    sheet = make_sheet()
    team = make_team("운영팀", ["alice@example.com"])
    link(sheet, team)

    assert team_service.delete_team(db, team.id) is True
    db.expire_all()
    assert db.query(Member).filter(Member.team_id == team.id).count() == 0
    assert db.query(SheetTeam).filter(SheetTeam.team_id == team.id).count() == 0
    assert db.query(SheetRegistration).filter(SheetRegistration.id == sheet.id).count() == 1


def test_시트_팀_연결_결과_코드(db, make_sheet, make_team):
    sheet = make_sheet()
    team = make_team("운영팀")
    assert sheet_service.link_team(db, sheet.id, team.id) == "ok"
    assert sheet_service.link_team(db, sheet.id, team.id) == "already"
    assert sheet_service.link_team(db, sheet.id, 9999) == "no_team"
    assert sheet_service.link_team(db, 9999, team.id) == "no_sheet"


def test_팀별_시트_조회(db, make_sheet, make_team, link):
    only_a = make_sheet("A팀 근무표")
    shared = make_sheet("공용 회의")
    a = make_team("A팀")
    b = make_team("B팀")
    link(only_a, a)
    link(shared, a)
    link(shared, b)

    assert [s.name for s in sheet_service.list_sheets(db, team_id=a.id)] == ["A팀 근무표", "공용 회의"]
    assert [s.name for s in sheet_service.list_sheets(db, team_id=b.id)] == ["공용 회의"]
    assert len(sheet_service.list_sheets(db)) == 2
