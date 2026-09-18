"""Automated secret and credential redaction engine."""

import json
import re
from typing import Any

# Compiled regex patterns for redaction
REDACTION_RULES: list[tuple[re.Pattern, str]] = [
    # Private keys (RSA, EC, DSA, OpenSSH)
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]+PRIVATE KEY-----",
            re.MULTILINE,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # AWS Access Key IDs
    (
        re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    # GitHub personal access tokens
    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    # GitLab personal access tokens
    (
        re.compile(r"\bglpat-[a-zA-Z0-9\-]{20,}\b"),
        "[REDACTED_GITLAB_TOKEN]",
    ),
    # Telegram Bot API Tokens (e.g. 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ)
    (
        re.compile(r"\b\d{8,11}:[a-zA-Z0-9_-]{35}\b"),
        "[REDACTED_TELEGRAM_TOKEN]",
    ),
    # Bearer tokens in headers or strings
    (
        re.compile(r"\bBearer\s+[a-zA-Z0-9\-_\.]{20,}\b", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    # OpenAI / Anthropic / SaaS AI API keys (sk-...)
    (
        re.compile(r"\bsk-[a-zA-Z0-9\-_]{20,}\b"),
        "[REDACTED_API_KEY]",
    ),
    # Database connection URIs with embedded passwords
    (
        re.compile(
            r"\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/)([^:\s\/]+):([^@\s\/]+)@([^\s\/]+)",
            re.IGNORECASE,
        ),
        r"\1\2:[REDACTED_PASSWORD]@\4",
    ),
    # Generic credential assignment in configs or shell commands (e.g. OPENAI_API_KEY="...", password: "...")
    (
        re.compile(
            r"(?i)\b([a-z0-9_-]*(?:password|passwd|secret|api_key|access_key|auth_token)[a-z0-9_-]*)\s*([:=])\s*(['\"])[^\r\n'\"]{4,}\3"
        ),
        r"\1 \2 \3[REDACTED_SECRET]\3",
    ),
]


class SecretRedactor:
    """Scans and redacts sensitive credentials from strings, dicts, and JSON structures."""

    def __init__(self, custom_rules: list[tuple[str, str]] | None = None) -> None:
        self.rules: list[tuple[re.Pattern, str]] = list(REDACTION_RULES)
        if custom_rules:
            for pattern_str, repl in custom_rules:
                self.rules.append((re.compile(pattern_str), repl))

    def redact_text(self, text: str | None) -> str | None:
        """Redact known secret patterns from a string."""
        if not text:
            return text
        result = text
        for pattern, replacement in self.rules:
            result = pattern.sub(replacement, result)
        return result

    def redact_data(self, data: Any) -> Any:
        """Recursively redact strings within lists, dicts, or JSON payloads."""
        if data is None:
            return None
        if isinstance(data, str):
            # Check if string is a JSON payload
            stripped = data.strip()
            if (stripped.startswith("{") and stripped.endswith("}")) or (
                stripped.startswith("[") and stripped.endswith("]")
            ):
                try:
                    parsed = json.loads(stripped)
                    redacted_parsed = self.redact_data(parsed)
                    return json.dumps(redacted_parsed, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            return self.redact_text(data)
        elif isinstance(data, dict):
            new_dict: dict[str, Any] = {}
            for k, v in data.items():
                # If key itself suggests a secret, mask value directly
                if (
                    isinstance(k, str)
                    and re.search(
                        r"(?i)(password|secret|api_key|token|auth_key|private_key)",
                        k,
                    )
                    and isinstance(v, str)
                    and len(v) > 3
                ):
                    new_dict[k] = "[REDACTED_SECRET]"
                else:
                    new_dict[k] = self.redact_data(v)
            return new_dict
        elif isinstance(data, list):
            return [self.redact_data(item) for item in data]
        return data


default_redactor = SecretRedactor()
