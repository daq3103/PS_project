"""Gmail delivery uses verified TLS, handles failures, and never needs a real mailbox."""

import smtplib
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.modules.customer import password_reset


@pytest.fixture
def gmail(monkeypatch):
    settings = Settings(
        _env_file=None,
        app_public_url="http://localhost",
        password_reset_email_provider="gmail",
        gmail_user="pethome.test@gmail.com",
        gmail_app_password="abcd efgh ijkl mnop",
    )
    monkeypatch.setattr(password_reset, "get_settings", lambda: settings)
    return settings


def test_gmail_requires_credentials_and_safe_public_url(gmail):
    assert password_reset.delivery_available()
    gmail.app_public_url = "http://example.com"
    assert not password_reset.delivery_available()
    gmail.app_public_url = "https://example.com"
    assert password_reset.delivery_available()
    gmail.gmail_user = ""
    assert not password_reset.delivery_available()


def test_gmail_requires_app_password(gmail):
    from pydantic import SecretStr

    gmail.gmail_app_password = SecretStr("")
    assert not password_reset.delivery_available()


@pytest.mark.asyncio
async def test_gmail_sends_multipart_link_over_tls(gmail, monkeypatch):
    smtp = MagicMock()
    client = smtp.return_value.__enter__.return_value
    client.send_message.return_value = {}
    monkeypatch.setattr(password_reset.smtplib, "SMTP_SSL", smtp)
    await password_reset.send_reset_code_email("recipient@gmail.com", "one-use-token")
    assert smtp.call_args.args == ("smtp.gmail.com", 465)
    context = smtp.call_args.kwargs["context"]
    assert context.check_hostname
    client.login.assert_called_once_with("pethome.test@gmail.com", "abcdefghijklmnop")
    message = client.send_message.call_args.args[0]
    assert message["To"] == "recipient@gmail.com"
    assert "one-use-token" in message.get_body(
        preferencelist=("plain",)
    ).get_content()
    assert "Mã đặt lại mật khẩu" in message.get_body(preferencelist=("html",)).get_content()


@pytest.mark.asyncio
async def test_gmail_delivers_code_without_a_reset_link(gmail, monkeypatch):
    smtp = MagicMock()
    client = smtp.return_value.__enter__.return_value
    client.send_message.return_value = {}
    monkeypatch.setattr(password_reset.smtplib, "SMTP_SSL", smtp)
    await password_reset.send_reset_code_email("recipient@gmail.com", "012345")
    message = client.send_message.call_args.args[0]
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "012345" in body and "10 phút" in body
    assert "reset-password?token=" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad credentials"),
                                  TimeoutError("connection timeout")])
async def test_gmail_failure_returns_safe_error(gmail, monkeypatch, error):
    smtp = MagicMock(side_effect=error)
    monkeypatch.setattr(password_reset.smtplib, "SMTP_SSL", smtp)
    with pytest.raises(HTTPException) as result:
        await password_reset.send_reset_code_email("recipient@gmail.com", "secret-token")
    assert result.value.status_code == 503
    assert "secret-token" not in result.value.detail


@pytest.mark.asyncio
async def test_resend_still_works(gmail, monkeypatch):
    gmail.password_reset_email_provider = "resend"
    gmail.resend_api_key = "test-key"
    gmail.resend_from = "PetHome <hello@example.com>"
    assert password_reset.delivery_available()
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.post.return_value = MagicMock()
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(password_reset.httpx, "AsyncClient", lambda **kwargs: context)
    await password_reset.send_reset_code_email("recipient@gmail.com", "token")
    assert client.post.call_args.args == ("https://api.resend.com/emails",)
