"""기존 DB(sheet_registrations + team_members)를 팀 구조로 옮긴다.

현재 동작을 그대로 유지하는 것이 목표다 - 기존 팀원 전원이 들어간 기본 팀을 만들고,
기존 시트를 모두 그 팀에 연결한다. 옮긴 뒤에도 같은 사람이 같은 알림을 받는다.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 프로젝트 루트에서 app 을 import

from app.config import DATABASE_URL, TZ
from app.database import Base, SessionLocal, engine
from app.models import Member, SheetRegistration, SheetTeam, Team

DEFAULT_TEAM = "기본"
db_path = Path(DATABASE_URL.replace("sqlite:///", "").lstrip("/")) if DATABASE_URL.startswith("sqlite") else None


def read_old_rows() -> tuple[list[dict], list[str]]:
    """옛 테이블을 SQLAlchemy 모델 없이 직접 읽는다 (모델은 이미 새 구조라서)."""
    if db_path is None or not db_path.exists():
        return [], []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    sheets, emails = [], []
    try:
        sheets = [dict(r) for r in con.execute("SELECT * FROM sheet_registrations")]
    except sqlite3.OperationalError:
        pass
    try:
        emails = [r["email"] for r in con.execute("SELECT email FROM team_members")]
    except sqlite3.OperationalError:
        pass
    con.close()
    return sheets, emails


def main() -> None:
    sheets, emails = read_old_rows()
    print(f"기존 데이터: 시트 {len(sheets)}개, 팀원 {len(emails)}명")

    if db_path and db_path.exists():
        backup = db_path.with_suffix(db_path.suffix + ".bak")
        shutil.copy2(db_path, backup)
        print(f"백업: {backup}")
        db_path.unlink()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        team = Team(name=DEFAULT_TEAM)
        db.add(team)
        db.flush()

        for email in emails:
            db.add(Member(team_id=team.id, email=email))

        for row in sheets:
            sheet = SheetRegistration(
                name=row["name"],
                sheet_id=row["sheet_id"],
                time_col=row["time_col"],
                data_cols=row["data_cols"],
                header_row=row["header_row"],
                time_format=row["time_format"],
                created_at=datetime.now(TZ),
            )
            db.add(sheet)
            db.flush()
            db.add(SheetTeam(sheet_id=sheet.id, team_id=team.id))

        db.commit()
        print(f"\n팀 {DEFAULT_TEAM!r} 생성 (id={team.id})")
        print(f"  멤버 {len(emails)}명: {emails}")
        print(f"  연결된 시트 {len(sheets)}개: {[s['name'] for s in sheets]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
