"""Unit tests for the /time, /quote, /beep, /bug, /stop, and /help bot helpers."""

from datetime import datetime, timezone
from random import Random
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

import bot


def test_format_help_lists_all_commands():
    text = bot.format_help()
    assert text.startswith("Available commands:")
    for name, description in bot.COMMANDS:
        assert name in text
        assert description in text
    assert "/help" in text
    assert "/time" in text
    assert "/quote" in text
    assert "/beep" in text
    assert "/bug" in text
    assert "/stop" in text
    assert "/start" in text


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


def test_bug_job_name_is_stable_per_chat():
    assert bot.bug_job_name(123) == "bug-hello-123"
    assert bot.bug_job_name(123) == bot.bug_job_name(123)
    assert bot.bug_job_name(1) != bot.bug_job_name(2)


def test_build_application_registers_handlers(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    app = bot.build_application("0000000000:TESTTOKEN-does-not-matter")
    assert app.bot_data["allowed_user_ids"] == {42}
    # start + help + time + quote + beep + bug + stop command handlers
    assert len(app.handlers[0]) == 7


def test_bug_interval_is_ten_minutes():
    assert bot.BUG_INTERVAL_SECONDS == 600


def _mock_update(user_id: int = 1, chat_id: int = 99):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _mock_context(allowed: set[int] | None = None, job_queue=None):
    context = MagicMock()
    context.application.bot_data = {"allowed_user_ids": allowed or set()}
    context.application.job_queue = job_queue
    return context


@pytest.mark.asyncio
async def test_bug_command_schedules_repeating_hello():
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    job_queue.run_repeating = MagicMock()
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue)

    await bot.bug_command(update, context)

    job_queue.run_repeating.assert_called_once_with(
        bot.send_bug_hello,
        interval=600,
        first=600,
        chat_id=50,
        name="bug-hello-50",
    )
    update.message.reply_text.assert_awaited()
    assert "10 minutes" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_bug_command_replaces_existing_job():
    old_job = MagicMock()
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = [old_job]
    job_queue.run_repeating = MagicMock()
    update = _mock_update(chat_id=7)
    context = _mock_context(job_queue=job_queue)

    await bot.bug_command(update, context)

    old_job.schedule_removal.assert_called_once()
    job_queue.run_repeating.assert_called_once()


@pytest.mark.asyncio
async def test_stop_command_removes_jobs():
    job = MagicMock()
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = [job]
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue)

    await bot.stop_command(update, context)

    job.schedule_removal.assert_called_once()
    update.message.reply_text.assert_awaited()
    assert "Stopped" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_stop_command_when_no_job():
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue)

    await bot.stop_command(update, context)

    update.message.reply_text.assert_awaited_with("No active /bug timer in this chat.")


@pytest.mark.asyncio
async def test_send_bug_hello_posts_hello():
    context = MagicMock()
    context.job = MagicMock()
    context.job.chat_id = 42
    context.bot.send_message = AsyncMock()

    await bot.send_bug_hello(context)

    context.bot.send_message.assert_awaited_once_with(chat_id=42, text="Hello!")
