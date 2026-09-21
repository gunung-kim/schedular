"""sheet_registrations 에 last_sent_row_at 컬럼을 추가한다.

재시작으로 같은 행이 다시 선택됐을 때 중복 발송을 막기 위한 기록이다.
SQLAlchemy 의 create_all 은 기존 테이블을 바꾸지 않으므로 직접 ALTER 한다.
여러 번 실행해도 안전하다.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATABASE_URL

COLUMN = "last_sent_row_at"
TABLE = "sheet_registrations"


def main() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        print("SQLite 전용 스크립트입니다.")
        return

    path = Path(DATABASE_URL.replace("sqlite:///", "").lstrip("/"))
    if not path.exists():
        print(f"{path} 가 없습니다. 서버를 한 번 띄우면 새 스키마로 생성됩니다.")
        return

    con = sqlite3.connect(path)
    existing = [r[1] for r in con.execute(f"PRAGMA table_info({TABLE})")]
    if COLUMN in existing:
        print(f"{COLUMN} 컬럼이 이미 있습니다. 변경 없음.")
    else:
        con.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} DATETIME")
        con.commit()
        print(f"{TABLE}.{COLUMN} 추가 완료")
    print("현재 컬럼:", [r[1] for r in con.execute(f"PRAGMA table_info({TABLE})")])
    con.close()


if __name__ == "__main__":
    main()
