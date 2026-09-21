# Sheet Scheduler

구글시트의 특정 행 데이터를 정해진 주기마다 읽어와 팀원들에게 이메일로 발송하는 스케줄러.

## 목적 / MVP 기능

1. 구글 시트 접속 후 데이터 읽기 (Google Sheets API)
2. 시트에서 "현재 시각"에 해당하는 행을 찾아 필요한 열 데이터 파싱
3. 파싱한 데이터를 팀원들에게 이메일 발송
4. 위 과정을 정해진 주기(기본 1시간)마다 자동 반복

시트마다 레이아웃(시간이 적힌 열, 데이터가 시작되는 행 등)이 다를 수 있으므로, 시트 등록 시 이 값들을 함께 지정한다. 현재는 **시간이 세로 열로 나열된 시트**만 지원한다 (가로 방향 지원은 이후 확장 예정).

## 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 웹 프레임워크 | FastAPI + Uvicorn | 요청 검증(Pydantic) 및 Swagger 문서(`/docs`)가 기본 내장되어 있어 관리용 API를 빠르게 구성 |
| DB | SQLite + SQLAlchemy | 테이블 2개, 저트래픽 내부 도구 수준이라 별도 DB 서버 불필요. 파일 하나로 백업/이동 가능 |
| 스케줄러 | APScheduler (BackgroundScheduler) | FastAPI 프로세스 안에서 함께 동작. Celery 등 별도 브로커/워커 불필요 |
| 시트 연동 | Google Sheets API v4 (서비스 계정 인증) | 사람 로그인 없이 서버가 자동으로 시트 읽기 가능 |
| 이메일 발송 | smtplib (Gmail SMTP, 앱 비밀번호) | 별도 이메일 발송 서비스 없이 표준 라이브러리로 처리 |

**왜 이 조합인가**
- Django는 관리자 페이지/템플릿 엔진 등 이 프로젝트에 안 쓰는 기능이 많아 제외. Flask 대비 FastAPI는 자동 API 문서화·요청 검증이 기본 제공되어 더 적은 코드로 동일한 걸 얻음.
- PostgreSQL/MySQL은 여러 서버·많은 동시 접속이 필요할 때 이점이 있는데, 지금은 단일 서버·낮은 쓰기 빈도라 SQLite로 충분.
- Celery+Redis는 여러 서버로 작업을 분산해야 하거나 대량 동시 작업이 필요할 때 쓰는 도구라 지금 규모엔 과함. Windows 환경 지원도 상대적으로 까다로움.
- OS 스케줄러(cron/launchd/Windows 작업 스케줄러)에 의존하면 Mac/Windows 환경마다 설정 방식이 달라져 유지보수가 번거로움 → 스케줄링 로직 자체를 Python 코드(APScheduler) 안에 내장해 OS에 상관없이 동일하게 동작하도록 함.

## 프로젝트 구조

```
schedular/
├── main.py                   # 실행 진입점 (python main.py)
├── requirements.txt
├── requirements-dev.txt       # 테스트 의존성
├── tests/                     # pytest (python -m pytest)
├── scripts/migrate_to_teams.py  # 구버전 DB → 팀 구조 이전
├── .env.example               # 환경변수 템플릿 (복사해서 .env로 사용)
├── service_account.json       # Google 서비스 계정 키 (직접 발급 후 배치, git에는 포함 안 함)
└── app/
    ├── main.py                    # FastAPI 앱 생성, 라우터/스케줄러 등록
    ├── config.py                   # .env 값 로드
    ├── database.py                 # SQLite 연결 및 세션
    ├── models.py                   # Team, Member, SheetRegistration, SheetTeam 테이블 정의
    ├── scheduler.py                 # 다음 행 시각을 예약하고 이어가는 체인 (언제 보낼지)
    ├── schemas/                     # [Schema] 요청/응답 검증
    │   ├── sheet.py
    │   └── team.py
    ├── routers/                     # [Router] HTTP 요청/응답만 처리, 로직은 service에 위임
    │   ├── sheets.py
    │   └── team.py
    ├── services/                    # [Service] 비즈니스 로직 + 외부 연동
    │   ├── sheet_service.py           # 시트 등록/조회/삭제, 팀 연결, 시간 매칭 로직
    │   ├── team_service.py            # 팀/멤버 등록(중복 검사)·조회·삭제
    │   ├── notification_service.py    # 행 읽기 + 수신자 조회 + 발송 (무엇을 보낼지)
    │   ├── google_sheets_client.py    # Google Sheets API 저수준 호출
    │   └── email_client.py            # SMTP 저수준 호출
    └── repositories/                # [Repository] DB 접근만 담당 (쿼리/커밋)
        ├── sheet_repository.py         # 시트 CRUD + 팀 연결
        ├── team_repository.py
        └── member_repository.py        # 멤버 CRUD + 시트별 수신자 조회
```

**레이어 간 의존 방향**: `router → service → repository → models`. 라우터는 DB를 직접 건드리지 않고 서비스만 호출하며, 서비스는 DB 세부사항(쿼리)을 모르고 리포지토리 함수만 호출한다. 구글시트/이메일처럼 외부 시스템 연동은 `*_client.py`로 분리해, 비즈니스 로직(`sheet_service.py`)이 "무엇을 할지"에 집중하고 "어떻게 호출할지"는 클라이언트가 담당하게 했다.

## 데이터 모델

**sheet_registrations** — 등록된 시트별 설정 (시트 URL 자체가 아니라 "어떻게 읽을지"의 설정만 저장)

| 컬럼 | 의미 | 예시 |
|---|---|---|
| name | 시트 구분용 이름 | "9월 근무표" |
| sheet_id | 시트 URL에서 추출한 ID | `1AbCd...` |
| time_col | 시간이 적힌 열 | `A` |
| data_cols | 발송할 데이터가 있는 열 범위 | `B:D` |
| header_row | 데이터가 시작되는 행 (제목행 제외) | `2` |
| time_format | 시간 셀의 표기 형식 (`datetime.strftime` 패턴) | `%H시` |

**teams** — 알림을 함께 받는 단위

| 컬럼 | 의미 |
|---|---|
| name | 팀 이름 (중복 불가) |

**members** — 팀에 속한 수신자. 한 멤버는 정확히 한 팀에 속한다.

| 컬럼 | 의미 |
|---|---|
| team_id | 소속 팀 (외래키, 팀 삭제 시 함께 삭제) |
| email | 수신자 이메일 |

같은 이메일이 여러 팀에 속할 수 있고, 같은 팀 안에서만 중복이 차단된다 (`UNIQUE(team_id, email)`).

**sheet_teams** — 시트와 팀의 연결 (중간 테이블)

| 컬럼 | 의미 |
|---|---|
| sheet_id | 시트 (외래키) |
| team_id | 팀 (외래키) |

한 시트를 여러 팀이 공유할 수 있고, 한 팀이 여러 시트를 쓸 수 있다. 그래서 어느 한쪽에 외래키를 두지 않고 중간 테이블로 뺐다.

**수신자 결정**: 시트 → 연결된 팀들 → 그 팀들의 멤버. 같은 사람이 이 시트를 공유하는 두 팀에 동시에 속해 있으면 중복 제거되어 한 통만 받는다.

> SQLite는 외래키 제약을 기본적으로 끈 채 동작하므로, `database.py`에서 연결할 때마다 `PRAGMA foreign_keys=ON`을 켠다. 이게 없으면 팀을 지워도 멤버와 연결이 그대로 남는다.

## 동작 흐름

시트마다 "다음 행 시각의 `NOTICE_LEAD_MINUTES`(기본 10분) 전"에만 실행되는 1회성 작업을 예약하고, 발송이 끝나면 그다음 행을 찾아 다시 예약하는 체인 방식으로 동작한다 (고정 간격으로 전체를 스캔하지 않음).

1. 시트가 등록되거나 서버가 시작될 때: `time_col`을 읽어 현재 시각 이후로 가장 가까운 행 시각을 찾는다 (오늘 남은 행이 없으면 내일 첫 행으로 넘어감)
2. 그 행 시각의 `NOTICE_LEAD_MINUTES`분 전을 발송 시각으로 예약
3. 예약된 시각이 되면: `time_col`을 다시 읽어 해당 행을 재확인하고 `data_cols` 값을 가져와 **그 시트에 연결된 팀들의 멤버 전원**에게 발송 (중복 제거)
4. 발송 직후, 방금 처리한 행 이후의 다음 행을 찾아 2번부터 반복 (모든 행을 다 돌면 다음 날 첫 행으로 순환)
5. 시트가 삭제되면 예약된 작업도 함께 취소됨

## 테스트

```bash
pip install -r requirements-dev.txt
python -m pytest
```

실제 구글 시트나 SMTP 는 타지 않는다. `tests/conftest.py`의 `no_network` 픽스처가 네트워크 호출을 막고 있어서, 스텁을 설치하지 않은 테스트가 밖으로 나가려 하면 그 자리에서 실패한다. DB 도 임시 파일을 쓰므로 `app.db` 는 건드리지 않는다.

| 파일 | 검증 대상 |
|---|---|
| `test_sheet_service.py` | 시각 파싱, 다음 행 찾기, 지나간 행 건너뛰기, 타임존 |
| `test_scheduler.py` | 체인 유지, 재시도, 감시 job, 늦은 알림 처리 |
| `test_teams.py` | 팀/멤버/연결, 수신자 라우팅, 중복 제거, CASCADE 삭제 |
| `test_email_client.py` | 숨은참조(Bcc), 한글 인코딩 |
| `test_api.py` | 라우터 오류 코드, 입력 검증 |

`test_scheduler.py`가 지키는 것들은 전부 운영 중 실제로 한 번씩 터졌던 문제다 — 체인이 조용히 멈추거나, 잠자기에서 깨어나며 밀린 알림이 쏟아지거나, 감시 job 이 정상 상태를 고장으로 오해하는 경우.

## 상세 가이드

- 최초 설정(Google Cloud, 서비스 계정, Gmail 앱 비밀번호 등): [docs/SETUP.md](docs/SETUP.md)
- 실행 및 API 사용법: [docs/USAGE.md](docs/USAGE.md)
