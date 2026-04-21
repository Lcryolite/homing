"""Tests for the logging sanitisation filter (T0.4)."""

import logging

from openemail.utils.logging_config import SensitiveDataFilter


def _make_record(msg: str) -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, "", 0, msg, (), None)


class TestSensitiveDataFilter:
    """Ensure SensitiveDataFilter masks secrets in log output."""

    def test_bearer_token(self):
        filt = SensitiveDataFilter()
        rec = _make_record("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        filt.filter(rec)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in rec.msg
        assert "***REDACTED***" in rec.msg

    def test_password_field(self):
        filt = SensitiveDataFilter()
        rec = _make_record('password="hunter2024secret"')
        filt.filter(rec)
        assert "hunter2024secret" not in rec.msg
        assert "***REDACTED***" in rec.msg

    def test_refresh_token(self):
        filt = SensitiveDataFilter()
        rec = _make_record("refresh_token=1//0abcABCdefGHIjklMNOpqrSTUvwxYZ1234567890")
        filt.filter(rec)
        assert "1//0abcABCdefGHIjklMNOpqrSTUvwxYZ1234567890" not in rec.msg
        assert "***REDACTED***" in rec.msg

    def test_cookie_header(self):
        filt = SensitiveDataFilter()
        rec = _make_record("Cookie: session_id=abc123def456ghi789jkl012mno345pqr")
        filt.filter(rec)
        assert "abc123def456ghi789jkl012mno345pqr" not in rec.msg
        assert "***REDACTED***" in rec.msg

    def test_clean_message_passthrough(self):
        filt = SensitiveDataFilter()
        rec = _make_record("Connection to imap.example.com successful")
        filt.filter(rec)
        assert rec.msg == "Connection to imap.example.com successful"

    def test_args_redaction(self):
        filt = SensitiveDataFilter()
        rec = _make_record("Auth: %s")
        rec.args = ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",)
        filt.filter(rec)
        assert "***REDACTED***" in rec.args[0]
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in rec.args[0]
