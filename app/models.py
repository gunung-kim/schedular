from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.config import TZ
from app.database import Base


class SheetRegistration(Base):
    __tablename__ = "sheet_registrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sheet_id = Column(String, nullable=False)
    time_col = Column(String, nullable=False)          # 예: "A"
    data_cols = Column(String, nullable=False)          # 예: "B:D"
    header_row = Column(Integer, nullable=False, default=1)  # 데이터가 시작되는 행 번호 (1부터 시작, 제목행 제외)
    time_format = Column(String, nullable=False, default="%H시")  # time_col 각 셀과 대조할 strftime 패턴
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TZ))


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TZ))
