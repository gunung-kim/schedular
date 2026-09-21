from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.config import TZ
from app.database import Base


class Team(Base):
    """알림을 함께 받는 단위. 시트는 팀에 연결되고, 그 팀의 멤버에게만 발송된다."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TZ))


class Member(Base):
    """팀에 속한 수신자. 한 멤버는 정확히 한 팀에 속한다."""

    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TZ))

    # 같은 팀 안에서만 중복을 막는다. 같은 사람이 여러 팀에 속하는 것은 허용한다.
    __table_args__ = (UniqueConstraint("team_id", "email", name="uq_member_team_email"),)


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


class SheetTeam(Base):
    """시트와 팀의 연결. 한 시트를 여러 팀이 공유할 수 있고, 한 팀이 여러 시트를 쓸 수 있다.
    그래서 어느 한쪽에 외래키를 두지 않고 중간 테이블로 뺐다."""

    __tablename__ = "sheet_teams"

    sheet_id = Column(Integer, ForeignKey("sheet_registrations.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TZ))
