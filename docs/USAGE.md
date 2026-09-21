# 사용법

[docs/SETUP.md](SETUP.md)의 최초 설정(가상환경, 서비스 계정, `.env`)이 끝났다는 전제로 설명한다.

## 서버 실행

```bash
source .venv/bin/activate      # Windows는: .venv\Scripts\activate
python main.py
```

기본 포트는 8000번이다. 이미 다른 프로세스가 8000번을 쓰고 있다면 아래처럼 포트를 바꿔 실행한다.

```bash
uvicorn app.main:app --reload --port 8001
```

정상 기동되면 브라우저에서 `http://localhost:8000/docs`(Swagger 문서)로 접속해 API를 직접 호출/테스트할 수 있다. 현재는 별도 관리 화면이 없고 이 Swagger 문서가 유일한 조작 인터페이스다.

## 팀 등록 (알림 받을 사람 묶기)

알림은 **팀 단위**로 나간다. 팀을 만들고, 멤버를 넣고, 시트를 그 팀에 연결하면 그 팀 멤버에게만 발송된다.

**1. 팀 만들기**

```bash
curl -X POST http://localhost:8000/teams \
  -H "Content-Type: application/json" \
  -d '{"name": "운영팀"}'
```

- 조회: `GET /teams`
- 삭제: `DELETE /teams/{team_id}` — 소속 멤버도 함께 삭제된다. 시트는 다른 팀이 공유할 수 있으므로 연결만 끊기고 남는다

**2. 팀에 멤버 넣기**

```bash
curl -X POST http://localhost:8000/teams/1/members \
  -H "Content-Type: application/json" \
  -d '{"email": "member@example.com"}'
```

- 조회: `GET /teams/{team_id}/members`
- 삭제: `DELETE /teams/{team_id}/members/{member_id}`

같은 이메일이 여러 팀에 속해도 된다. 같은 팀 안에서만 중복이 거부된다.

**3. 시트를 팀에 연결** (시트 등록 후)

```bash
curl -X POST http://localhost:8000/sheets/1/teams/1
```

- 연결된 팀 조회: `GET /sheets/{sheet_id}/teams`
- 연결 해제: `DELETE /sheets/{sheet_id}/teams/{team_id}`

**연결하지 않으면 수신자가 0명이라 알림이 나가지 않는다.** 시트를 등록한 뒤 이 단계를 잊지 않도록 주의한다.

한 시트를 여러 팀에 연결하면 모든 팀의 멤버가 받는다. 같은 사람이 두 팀에 속해 있어도 **한 통만** 간다.

## 시트 등록

```bash
curl -X POST http://localhost:8000/sheets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "9월 근무표",
    "sheet_url": "https://docs.google.com/spreadsheets/d/시트ID/edit",
    "time_col": "A",
    "data_cols": "B:D",
    "header_row": 2,
    "time_format": "%H시"
  }'
```

각 필드의 의미:

| 필드 | 의미 | 확인 방법 |
|---|---|---|
| `name` | 이 등록 건을 구분할 이름 (이메일 제목에 사용됨) | 자유롭게 지정 |
| `sheet_url` | 시트 URL 전체 (또는 시트 ID만) | 브라우저 주소창에서 복사 |
| `time_col` | 시간이 세로로 나열된 열 | 시트를 보고 확인 (예: A열) |
| `data_cols` | 발송할 데이터가 있는 열 범위 | 예: `B:D`이면 B, C, D열 값을 모두 이메일 본문에 포함 |
| `header_row` | 실제 데이터가 시작되는 행 번호 (제목행 제외) | 예: 1행이 제목이면 `2` |
| `time_format` | 시간 셀에 실제로 적힌 표기와 정확히 일치해야 하는 형식 | 아래 표 참고 |

`time_format` 예시 (Python `strftime` 형식):

| 시트에 적힌 표기 | `time_format` 값 |
|---|---|
| `09시` | `%H시` |
| `9:00` | `%H:%M` |
| `오전 9시` | 지원 안 됨 — 시트를 24시간제(`09시`, `9:00` 등)로 바꾸는 것을 권장 (MVP는 24시간제 위주로 검증됨) |

- 조회: `GET /sheets`
- 삭제: `DELETE /sheets/{id}`
- 팀별 조회: `GET /sheets?team_id=1` — 그 팀에 연결된 시트만

## 발송 테스트

설정이 맞는지 예약 시각까지 기다리지 않고 바로 확인할 수 있다. 다음 행 기준으로 **실제 메일이 한 통 발송**된다.

```bash
curl -X POST http://localhost:8000/sheets/1/test
```

```json
{
  "row_time": "2026-09-09T02:00:00+09:00",
  "subject": "[근무표] 02:00 알림",
  "body": "당직 김",
  "recipients": ["member@example.com"]
}
```

예약된 일정은 건드리지 않으므로, 정규 발송은 원래대로 진행된다.

| 응답 | 의미 |
|---|---|
| `404` | 해당 id의 시트가 없음 |
| `400` | 시트에 연결된 팀이 없음(수신자 0명) / 파싱 가능한 시간 행 없음 / 일치하는 행 없음 |
| `502` | 시트를 읽지 못함(권한·네트워크) 또는 메일 발송 실패 |

## 동작 확인

- 시트를 등록하면 그 시트에서 현재 시각 이후 가장 가까운 행을 찾아, 그 행 시각의 `NOTICE_LEAD_MINUTES`(기본 10분) 전에 자동으로 확인·발송하도록 예약된다. 예약을 기다리지 않고 지금 바로 확인하려면 [발송 테스트](#발송-테스트)를 사용한다.
- 발송 후에는 다음 행을 찾아 같은 방식으로 다시 예약된다 (마지막 행까지 다 돌면 다음 날 첫 행으로 순환).
- 수신자는 발송 시점에 다시 조회하므로, 이미 예약된 알림에도 멤버 추가/삭제가 즉시 반영된다.
- 서버 콘솔 로그에 시트별 처리 결과가 출력된다.
  - `[시트이름] 다음 알림 ... (행 시각 ...)` — 다음 발송이 예약됨
  - `[시트이름] ...에 해당하는 행 없음` — 예약된 시각에 재확인했는데 해당 행을 못 찾음 (그 사이 시트가 수정된 경우 등)
  - `[시트이름] ... 발송 완료 (수신자 N명)` — 정상 발송됨
  - `[id] ... - ...에 예약 재시도` — 시트를 읽지 못해 `SCHEDULE_RETRY_MINUTES` 뒤 재시도로 넘어감
  - `[id] 다음 알림 예약 실패` / `[id] ... 발송 실패` — 오류 발생 (아래 원인 참고)

## 자주 발생하는 문제

- **메일이 아예 안 옴**: 시트에 팀이 연결돼 있는지 먼저 확인한다 (`GET /sheets/{id}/teams`). 연결된 팀이 없으면 수신자가 0명이라 조용히 발송되지 않는다. 그리고 서버가 떠 있어야 스케줄러가 동작한다. 먼저 [발송 테스트](#발송-테스트)로 설정 자체가 맞는지 확인하는 것이 빠르다
- **403 / 권한 오류**: 해당 시트가 서비스 계정 이메일과 공유되어 있는지 확인 ([SETUP.md](SETUP.md) 4단계)
- **이메일 발송 실패 (SMTP 인증 오류)**: `SENDER_APP_PASSWORD`가 일반 로그인 비밀번호가 아니라 앱 비밀번호인지, 공백 없이 입력했는지 확인
- **매칭되는 행이 없음**: 시트에 적힌 시간 표기와 `time_format`이 정확히 일치하는지 확인 (예: 시트엔 `9시`인데 `time_format`을 `%H시`(09시 기대)로 설정하면 불일치)
- **서버 실행 시 포트 충돌**: 8000번 포트를 다른 프로세스가 쓰고 있다면 `--port` 옵션으로 다른 포트 지정
