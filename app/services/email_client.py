import smtplib
from email.mime.text import MIMEText

from app.config import SENDER_APP_PASSWORD, SENDER_EMAIL, SMTP_HOST, SMTP_PORT


def send_email(subject: str, body: str, recipients: list[str]) -> None:
    """팀원 전원에게 숨은참조(Bcc)로 발송한다.

    실제 배달은 헤더가 아니라 sendmail()에 넘기는 봉투(recipients)가 결정하므로,
    To 헤더에서 명단을 빼도 전원에게 그대로 배달된다.
    Bcc 헤더는 따로 넣지 않는다 - 메일 서버 구현에 따라 명단이 노출될 수 있고,
    봉투에만 주소를 두는 것으로 숨은참조는 이미 성립한다."""
    if not recipients:
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = SENDER_EMAIL  # 수신자 명단이 서로에게 보이지 않도록 발신자 본인만 표기

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
