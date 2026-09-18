"""Tests for the secret and credential redaction engine."""

from hermes_share.redactor import SecretRedactor


def test_redact_api_keys():
    redactor = SecretRedactor()
    text = "Here is my key: sk-abcdef1234567890abcdef1234567890 and use it well."
    assert "sk-" not in redactor.redact_text(text)
    assert "[REDACTED_API_KEY]" in redactor.redact_text(text)


def test_redact_github_tokens():
    redactor = SecretRedactor()
    text = "Clone with ghp_123456789012345678901234567890123456 please."
    assert "ghp_" not in redactor.redact_text(text)
    assert "[REDACTED_GITHUB_TOKEN]" in redactor.redact_text(text)


def test_redact_telegram_tokens():
    redactor = SecretRedactor()
    text = "Bot token is 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ123456789."
    assert "123456789:" not in redactor.redact_text(text)
    assert "[REDACTED_TELEGRAM_TOKEN]" in redactor.redact_text(text)


def test_redact_bearer_tokens():
    redactor = SecretRedactor()
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sign"
    assert "Bearer [REDACTED_TOKEN]" in redactor.redact_text(text)


def test_redact_private_keys():
    redactor = SecretRedactor()
    key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1+...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    assert redactor.redact_text(key) == "[REDACTED_PRIVATE_KEY]"


def test_redact_database_uris():
    redactor = SecretRedactor()
    uri = "postgres://admin:supersecretpassword123@db.internal.lan:5432/mydb"
    redacted = redactor.redact_text(uri)
    assert "supersecretpassword123" not in redacted
    assert "postgres://admin:[REDACTED_PASSWORD]@db.internal.lan:5432/mydb" == redacted


def test_redact_json_nested():
    redactor = SecretRedactor()
    payload = {
        "command": "export OPENAI_API_KEY='sk-11112222333344445555666677778888'",
        "nested": {
            "token": "gho_123456789012345678901234567890123456",
            "db": "mysql://user:pass12345@localhost/app",
        },
    }
    redacted = redactor.redact_data(payload)
    assert "[REDACTED_SECRET]" in redacted["command"] or "[REDACTED_API_KEY]" in redacted["command"]
    assert "[REDACTED_SECRET]" in redacted["nested"]["token"] or "[REDACTED_GITHUB_TOKEN]" in redacted["nested"]["token"]
    assert "pass12345" not in redacted["nested"]["db"]
