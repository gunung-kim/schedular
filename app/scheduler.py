import logging
from datetime import datetime, timedelta

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import (
    NOTICE_LEAD_MINUTES,
    SCHEDULE_RETRY_MINUTES,
    TZ,
    WATCHDOG_INTERVAL_MINUTES,
)
from app.database import SessionLocal
from app.repositories import member_repository, sheet_repository
from app.services import notification_service, sheet_service

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(timezone=TZ)

_WATCHDOG_JOB_ID = "watchdog"

# 지금 _fire 가 처리 중인 시트. 감시 job 이 "예약 없음"으로 오해해
# 중복 발송을 거는 것을 막는다 (실행 중에는 그 시트의 job 이 잠시 사라진 상태다).
_in_flight: set[int] = set()


def _job_id(registration_id: int) -> str:
    return f"sheet_notice_{registration_id}"


def _add_job(func, run_at: datetime, registration_id: int, *args) -> None:
    """시트 하나에 걸려 있는 단 하나의 예약 작업을 등록한다.
    한 시트는 같은 시점에 발송 작업이든 재시도 작업이든 하나만 가지므로,
    같은 id를 공유해 서로를 덮어쓰게 한다."""
    scheduler.add_job(
        func,
        "date",
        run_date=run_at,
        args=[registration_id, *args],
        id=_job_id(registration_id),
        replace_existing=True,
        misfire_grace_time=None,
    )


def _schedule_retry(registration_id: int, after: datetime | None, reason: str) -> None:
    """예약 단계 자체를 다시 시도하는 작업을 건다.
    이 시트가 아무 작업도 없는 상태로 방치되지 않게 하는 것이 목적이다."""
    retry_at = datetime.now(TZ) + timedelta(minutes=SCHEDULE_RETRY_MINUTES)
    _add_job(_reschedule, retry_at, registration_id, after)
    logger.warning("[%d] %s - %s에 예약 재시도", registration_id, reason, retry_at)


def _book_next(registration_id: int, after: datetime | None) -> None:
    """`after`보다 엄격히 뒤에 있는 첫 행 시각을 찾아, 그보다 NOTICE_LEAD_MINUTES 앞선 시점에 발송 작업을 건다.
    실패 처리는 호출자인 `_reschedule`이 맡는다."""
    db = SessionLocal()
    try:
        registration = sheet_repository.get_by_id(db, registration_id)
        if registration is None:
            return  # 예약 후 삭제된 시트 - 여기서 체인을 끝내는 것이 맞다

        next_row_dt = sheet_service.find_next_row_time(registration, after=after)
        if next_row_dt is None:
            # 시트는 읽히지만 파싱 가능한 시간 행이 없는 상태.
            # 아직 비어 있을 뿐일 수 있으므로 포기하지 않고 계속 확인한다.
            _schedule_retry(registration_id, after, "파싱 가능한 시간 행 없음")
            return

        # 이미 알림 시점을 지난 경우(행 시각에 임박해 시트를 등록했거나, 재시도가 늦게 실행됨)
        # 과거 시각으로 예약하지 않고 가능한 한 빨리 발송한다.
        fire_at = max(next_row_dt - timedelta(minutes=NOTICE_LEAD_MINUTES), datetime.now(TZ))
        _add_job(_fire, fire_at, registration_id, next_row_dt)
        logger.info("[%s] 다음 알림 %s (행 시각 %s)", registration.name, fire_at, next_row_dt)
    finally:
        db.close()


def _reschedule(registration_id: int, after: datetime | None = None) -> None:
    """체인을 이어가는 유일한 지점이자 최종 안전장치.

    체인 방식이라 각 단계가 다음 단계를 예약해야만 알림이 이어진다.
    따라서 어떤 예외도 밖으로 던지지 않고 재시도를 걸어,
    시트가 다음 재시작 전까지 조용히 멈춰 있는 상황을 막는다."""
    try:
        _book_next(registration_id, after)
    except Exception:
        logger.exception("[%d] 다음 알림 예약 실패", registration_id)
        _schedule_retry(registration_id, after, "예약 처리 중 오류")


def _already_sent(registration, target_dt: datetime) -> bool:
    """이 행을 이미 발송했는지. 재시작으로 같은 행이 다시 선택됐을 때를 걸러낸다.

    SQLite 는 tzinfo 를 보존하지 않아 읽어올 때 naive 가 되므로,
    비교 전에 설정된 타임존을 다시 붙인다 (저장할 때는 항상 그 타임존의 값이다)."""
    last = registration.last_sent_row_at
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=TZ)
    return last == target_dt


def _send_notice(registration_id: int, target_dt: datetime) -> bool:
    """`target_dt`와 일치하는 행을 시트에서 다시 읽어 팀원들에게 발송한다.
    시트 등록이 이미 삭제되어 이어갈 체인이 없으면 False를 반환한다."""
    db = SessionLocal()
    try:
        registration = sheet_repository.get_by_id(db, registration_id)
        if registration is None:
            return False

        if _already_sent(registration, target_dt):
            logger.info("[%s] %s 는 이미 발송함 - 건너뜀 (재시작 등으로 다시 선택된 행)",
                        registration.name, target_dt)
            return True

        # 수신자 확인을 시트 읽기보다 먼저 한다. 연결된 팀이 없으면 어차피 아무도 못 받으므로
        # 구글 API 를 호출할 이유가 없다. 발송만 건너뛰고 체인은 이어가므로,
        # 나중에 팀을 연결하면 다음 행부터 자동으로 발송이 재개된다.
        if not member_repository.get_emails_for_sheet(db, registration_id):
            logger.warning(
                "[%s] 연결된 팀이 없어 발송하지 않음 - POST /sheets/%d/teams/{team_id} 로 팀을 연결하세요",
                registration.name, registration_id,
            )
            return True

        result = notification_service.send_row_notice(db, registration, target_dt)
        if result is None:
            logger.info("[%s] %s에 해당하는 행 없음", registration.name, target_dt)
        else:
            logger.info("[%s] %s 발송 완료 (수신자 %d명)", registration.name, target_dt, len(result.recipients))
            sheet_repository.mark_sent(db, registration, target_dt)
        return True
    finally:
        db.close()


def _fire(registration_id: int, target_dt: datetime) -> None:
    """예약된 시각에 실행되는 작업. 발송하고, 이어서 다음 알림을 예약한다.
    발송이 실패해도 체인은 계속 이어간다."""
    _in_flight.add(registration_id)
    try:
        # 잠자기 등으로 job 이 한참 늦게 실행된 경우. 행 시각 자체가 이미 지났고
        # 유예(NOTICE_LEAD_MINUTES)까지 넘겼다면 지금 보내도 의미가 없으므로 건너뛴다.
        # 발송만 건너뛰고 체인은 그대로 이어 다음 행을 예약한다.
        overdue_by = datetime.now(TZ) - target_dt
        if overdue_by > timedelta(minutes=NOTICE_LEAD_MINUTES):
            logger.warning("[%d] %s 알림이 %s 늦어 건너뜀", registration_id, target_dt, overdue_by)
        else:
            try:
                if not _send_notice(registration_id, target_dt):
                    return  # 예약 후 삭제된 시트 - 체인 종료
            except Exception:
                logger.exception("[%d] %s 발송 실패", registration_id, target_dt)
        _reschedule(registration_id, after=target_dt)
    finally:
        _in_flight.discard(registration_id)


def _watchdog() -> None:
    """예약이 사라진 시트를 찾아 다시 건다.

    APScheduler 는 같은 id 의 job 이 실행 중일 때 새로 등록된 job 을 예외 없이 버린다
    (`skipped: maximum number of running instances reached`). 이렇게 조용히 사라지는
    경우는 예외 기반 재시도로 잡히지 않으므로, 주기적으로 훑어서 복구한다."""
    db = SessionLocal()
    try:
        registration_ids = [r.id for r in sheet_repository.get_all(db)]
    finally:
        db.close()

    for registration_id in registration_ids:
        if registration_id in _in_flight:
            continue  # 처리 중이라 job 이 잠시 없는 것뿐이다
        if scheduler.get_job(_job_id(registration_id)) is None:
            logger.warning("[%d] 예약이 사라져 있어 다시 예약한다", registration_id)
            _reschedule(registration_id)


def schedule_sheet(registration_id: int) -> None:
    """시트의 첫 발송 작업을 예약한다 (시트 등록 시 또는 서버 시작 시)."""
    _reschedule(registration_id, after=None)


def unschedule_sheet(registration_id: int) -> None:
    try:
        scheduler.remove_job(_job_id(registration_id))
    except JobLookupError:
        pass


def start_scheduler():
    db = SessionLocal()
    try:
        registration_ids = [r.id for r in sheet_repository.get_all(db)]
    finally:
        db.close()

    for registration_id in registration_ids:
        schedule_sheet(registration_id)

    scheduler.add_job(
        _watchdog,
        "interval",
        minutes=WATCHDOG_INTERVAL_MINUTES,
        id=_WATCHDOG_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
