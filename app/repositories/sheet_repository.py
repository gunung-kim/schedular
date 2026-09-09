from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SheetRegistration


def create(db: Session, sheet: SheetRegistration) -> SheetRegistration:
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet


def get_all(db: Session) -> list[SheetRegistration]:
    return list(db.execute(select(SheetRegistration)).scalars().all())


def get_by_id(db: Session, sheet_id: int) -> SheetRegistration | None:
    stmt = select(SheetRegistration).where(SheetRegistration.id == sheet_id)
    return db.execute(stmt).scalar_one_or_none()


def delete(db: Session, sheet: SheetRegistration) -> None:
    db.delete(sheet)
    db.commit()
