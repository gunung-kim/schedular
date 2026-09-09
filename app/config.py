import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# 시트에 적힌 시각("09시" 등)을 해석하는 기준 타임존.
# 서버 OS의 시간대(도커/클라우드는 대개 UTC)와 무관하게 항상 같은 시각에 동작하도록 명시한다.
TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")
TZ = ZoneInfo(TIMEZONE)

NOTICE_LEAD_MINUTES = int(os.getenv("NOTICE_LEAD_MINUTES", "10"))
SCHEDULE_RETRY_MINUTES = int(os.getenv("SCHEDULE_RETRY_MINUTES", "5"))

# 예약이 사라진 시트가 없는지 훑어보는 주기(분)
WATCHDOG_INTERVAL_MINUTES = int(os.getenv("WATCHDOG_INTERVAL_MINUTES", "15"))
