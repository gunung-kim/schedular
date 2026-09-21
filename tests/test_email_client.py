"""수신자 명단이 서로에게 노출되지 않는지(Bcc)."""
import smtplib
from email import message_from_string

from app.services import email_client

TEAM = ["alice@example.com", "bob@example.com", "carol@example.com"]


class _FakeSMTP:
    captured: dict = {}

    def __init__(self, host, port):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def sendmail(self, sender, envelope, raw):
        _FakeSMTP.captured = {"sender": sender, "envelope": envelope, "raw": raw}


def _send(monkeypatch, recipients=TEAM):
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)   # autouse 차단막을 이 테스트용 스텁으로 교체
    monkeypatch.setattr(email_client, "SENDER_EMAIL", "bot@example.com")
    monkeypatch.setattr(email_client, "SENDER_APP_PASSWORD", "app-password")
    _FakeSMTP.captured = {}
    email_client.send_email(subject="[근무표] 09:00 알림", body="줄1\n줄2", recipients=recipients)
    return _FakeSMTP.captured


def test_봉투에는_수신자_전원이_들어간다(monkeypatch):
    cap = _send(monkeypatch)
    assert cap["envelope"] == TEAM


def test_헤더에는_수신자가_노출되지_않는다(monkeypatch):
    cap = _send(monkeypatch)
    msg = message_from_string(cap["raw"])
    headers = "\n".join(f"{k}: {v}" for k, v in msg.items())
    assert msg["To"] == "bot@example.com"
    assert msg["Bcc"] is None
    assert not [a for a in TEAM if a in headers]


def test_한글_제목과_본문이_정상_복원된다(monkeypatch):
    from email.header import decode_header, make_header

    cap = _send(monkeypatch)
    msg = message_from_string(cap["raw"])
    assert str(make_header(decode_header(msg["Subject"]))) == "[근무표] 09:00 알림"
    assert msg.get_payload(decode=True).decode("utf-8").strip() == "줄1\n줄2"


def test_수신자가_없으면_접속조차_하지_않는다(monkeypatch):
    cap = _send(monkeypatch, recipients=[])
    assert cap == {}
