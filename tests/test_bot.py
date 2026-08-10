"""Unit tests for the /time and /quote bot helpers."""

from datetime import datetime, timezone
from random import Random
from zoneinfo import ZoneInfo

import bot


def test_format_system_time_includes_utc_and_local():
    fixed = datetime(2026, 8, 10, 12, 30, 45, tzinfo=timezone.utc)
    text = bot.format_system_time(fixed)
    assert "System time (UTC): 2026-08-10 12:30:45 UTC" in text
    assert "System time (local):" in text


def test_format_system_time_naive_treated_as_utc():
    fixed = datetime(2026, 1, 1, 0, 0, 0)
    text = bot.format_system_time(fixed)
    assert "2026-01-01 00:00:00 UTC" in text


def test_format_system_time_converts_other_zones():
    fixed = datetime(2026, 8, 10, 8, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    text = bot.format_system_time(fixed)
    assert "2026-08-10 12:00:00 UTC" in text


def test_quotes_has_ten_entries():
    assert len(bot.QUOTES) == 10
    for text, author in bot.QUOTES:
        assert text
        assert author


def test_format_quote():
    assert bot.format_quote("Hello", "Ada") == '"Hello"\n— Ada'


def test_random_quote_is_deterministic_with_seeded_rng():
    text = bot.random_quote(Random(0))
    assert text.startswith('"')
    assert "—" in text
    # Must match one of the built-in quotes
    assert any(text == bot.format_quote(q, a) for q, a in bot.QUOTES)


def test_allowed_user_ids_empty(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_ID", raising=False)
    assert bot.allowed_user_ids() == set()


def test_allowed_user_ids_parses_csv(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "111, 222,333")
    assert bot.allowed_user_ids() == {111, 222, 333}


def test_build_application_registers_handlers(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    app = bot.build_application("0000000000:TESTTOKEN-does-not-matter")
    assert app.bot_data["allowed_user_ids"] == {42}
    # start + time + quote command handlers
    assert len(app.handlers[0]) == 3
