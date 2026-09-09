# 최초 설정 가이드

프로젝트를 처음 연동할 때 한 번만 하면 되는 작업들이다. 아래 순서대로 진행한다.

## 1. Python 환경 준비

```bash
cd schedular
python3 -m venv .venv
source .venv/bin/activate      # Windows는: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Google Cloud 프로젝트 생성 및 Sheets API 활성화

1. https://console.cloud.google.com/ 접속 (구글 계정 로그인)
2. 상단 "프로젝트 선택" → "새 프로젝트" → 이름 입력(예: `sheet-scheduler`) 후 생성
   - 결제/카드 등록 없이 무료로 진행 가능. "$300 무료 크레딧" 배너는 무시해도 됨
3. 생성한 프로젝트가 상단에 선택된 상태에서, 검색창에 `Google Sheets API` 검색 → 클릭 → **사용(Enable)**

## 3. 서비스 계정 생성 및 키 발급

서비스 계정은 "사람이 로그인하지 않아도 서버가 자동으로 구글시트를 읽을 수 있게 해주는 전용 계정"이다.

1. 좌측 메뉴 → **API 및 서비스 → 사용자 인증 정보**
2. 상단 **+ 사용자 인증 정보 만들기 → 서비스 계정**
3. 이름 입력(예: `sheet-scheduler-bot`) → 만들고 계속하기 → 역할 지정은 건너뛰고 완료
4. 생성된 서비스 계정 이메일을 클릭 → **키(Keys) 탭 → 키 추가 → 새 키 만들기 → JSON** 선택 → 다운로드
5. 다운로드된 파일을 프로젝트 루트로 옮기고 이름을 `service_account.json`으로 변경

```
schedular/service_account.json
```

이 파일은 `.gitignore`에 포함되어 있어 git에는 올라가지 않는다 (외부 유출 시 시트 접근 권한이 노출되므로 절대 커밋/공유하지 않는다).

서비스 계정 이메일(`...@...iam.gserviceaccount.com` 형태)은 이후 시트를 등록할 때마다 계속 필요하니 기억해둔다.

## 4. 대상 구글시트를 서비스 계정과 공유

발송에 사용할 각 구글시트마다 아래 작업이 필요하다 (매달 시트가 바뀌면 새 시트마다 반복).

1. 구글시트 열기 → 우측 상단 **공유** 클릭
2. 3번에서 만든 서비스 계정 이메일 입력
3. 권한을 **뷰어(Viewer)**로 설정
4. "Google 계정이 연결되어 있지 않다"는 경고가 뜨면 **이메일 알림 보내기 체크 → 공유/전송**, 이어서 "Google 이외의 계정과 공유하시겠습니까?" 확인창이 뜨면 **무시하고 공유** 클릭
   - 서비스 계정은 사람이 로그인하는 일반 계정이 아니라서 나오는 정상적인 경고이며, 본인이 직접 만든 서비스 계정 주소가 맞다면 진행해도 안전하다

## 5. Gmail 앱 비밀번호 발급 (발송 계정)

Gmail은 보안 정책상 일반 로그인 비밀번호로 외부 프로그램(SMTP) 로그인을 허용하지 않는다. 앱 전용 비밀번호를 별도로 발급받아야 한다.

1. 발송에 사용할 Gmail 계정에서 **2단계 인증**이 켜져 있는지 확인: https://myaccount.google.com/security
   - 꺼져 있으면 먼저 켠다 (휴대폰 인증 등 본인 확인 필요)
2. https://myaccount.google.com/apppasswords 접속
3. 앱 이름 입력(예: `sheet-scheduler`) → 생성
4. 표시되는 16자리 문자열을 복사 (화면엔 4자리씩 띄어서 보이지만, 실제 값은 공백 없이 이어 붙인 16자리)

## 6. 환경변수 설정

`.env.example`을 복사해 `.env` 파일을 만들고 값을 채운다.

```bash
cp .env.example .env
```

```env
DATABASE_URL=sqlite:///./app.db

GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json

SENDER_EMAIL=발송할Gmail주소@gmail.com
SENDER_APP_PASSWORD=위에서발급받은16자리값(공백없이)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465

NOTICE_LEAD_MINUTES=10
```

- `SMTP_HOST`/`SMTP_PORT`는 Gmail 고정값이라 수정할 필요 없음
- `.env` 파일도 `.gitignore`에 포함되어 git에는 올라가지 않음 — 비밀번호가 담긴 파일이므로 절대 커밋하지 않는다

여기까지 완료되면 [docs/USAGE.md](USAGE.md)를 따라 서버를 실행하고 시트/팀원을 등록한다.
