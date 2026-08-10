"""Unit tests for the /time, /quote, /beep, /bug, /config, /stop, and /help bot helpers."""

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
    assert "/config" in text
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
    assert app.bot_data[bot.BUG_INTERVAL_KEY] == 600
    # start + help + time + quote + beep + bug + config + stop command handlers
    assert len(app.handlers[0]) == 8


def test_bug_interval_default_is_ten_minutes():
    assert bot.BUG_INTERVAL_SECONDS == 600
    assert bot.DEFAULT_BUG_INTERVAL_MINUTES == 10
    assert bot.get_bug_interval_seconds({}) == 600
    assert bot.get_bug_interval_minutes({}) == 10


def test_set_and_get_bug_interval_minutes():
    data: dict = {}
    assert bot.set_bug_interval_minutes(data, 5) == 5
    assert data[bot.BUG_INTERVAL_KEY] == 300
    assert bot.get_bug_interval_minutes(data) == 5
    assert bot.get_bug_interval_seconds(data) == 300


def test_set_bug_interval_minutes_rejects_out_of_range():
    with pytest.raises(ValueError):
        bot.set_bug_interval_minutes({}, 0)
    with pytest.raises(ValueError):
        bot.set_bug_interval_minutes({}, 24 * 60 + 1)


def test_parse_config_minutes():
    assert bot.parse_config_minutes(None) is None
    assert bot.parse_config_minutes([]) is None
    assert bot.parse_config_minutes(["3"]) == 3
    with pytest.raises(ValueError):
        bot.parse_config_minutes(["0"])
    with pytest.raises(ValueError):
        bot.parse_config_minutes(["nope"])
    with pytest.raises(ValueError):
        bot.parse_config_minutes(["1", "2"])


def test_format_minutes():
    assert bot.format_minutes(1) == "1 minute"
    assert bot.format_minutes(10) == "10 minutes"


def _mock_update(user_id: int = 1, chat_id: int = 99):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _mock_context(
    allowed: set[int] | None = None,
    job_queue=None,
    interval_seconds: int = 600,
    args: list[str] | None = None,
):
    context = MagicMock()
    context.application.bot_data = {
        "allowed_user_ids": allowed or set(),
        bot.BUG_INTERVAL_KEY: interval_seconds,
    }
    context.application.job_queue = job_queue
    context.args = args or []
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
async def test_bug_command_uses_configured_interval():
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    job_queue.run_repeating = MagicMock()
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue, interval_seconds=120)

    await bot.bug_command(update, context)

    job_queue.run_repeating.assert_called_once_with(
        bot.send_bug_hello,
        interval=120,
        first=120,
        chat_id=50,
        name="bug-hello-50",
    )
    assert "2 minutes" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_config_command_shows_current_when_no_args():
    update = _mock_update()
    context = _mock_context(interval_seconds=600, args=[])

    await bot.config_command(update, context)

    update.message.reply_text.assert_awaited()
    text = update.message.reply_text.await_args.args[0]
    assert "10 minutes" in text
    assert "/config <minutes>" in text


@pytest.mark.asyncio
async def test_config_command_sets_interval():
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue, args=["5"])

    await bot.config_command(update, context)

    assert context.application.bot_data[bot.BUG_INTERVAL_KEY] == 300
    update.message.reply_text.assert_awaited_with("Bug interval set to 5 minutes.")


@pytest.mark.asyncio
async def test_config_command_reschedules_active_bug():
    old_job = MagicMock()
    job_queue = MagicMock()
    # first get_jobs_by_name: check active; second+ inside _schedule_bug_job: remove
    job_queue.get_jobs_by_name.return_value = [old_job]
    job_queue.run_repeating = MagicMock()
    update = _mock_update(chat_id=50)
    context = _mock_context(job_queue=job_queue, args=["1"])

    await bot.config_command(update, context)

    assert context.application.bot_data[bot.BUG_INTERVAL_KEY] == 60
    job_queue.run_repeating.assert_called_once_with(
        bot.send_bug_hello,
        interval=60,
        first=60,
        chat_id=50,
        name="bug-hello-50",
    )
    text = update.message.reply_text.await_args.args[0]
    assert "1 minute" in text
    assert "Active /bug timer updated" in text


@pytest.mark.asyncio
async def test_config_command_rejects_invalid():
    update = _mock_update()
    context = _mock_context(args=["abc"])

    await bot.config_command(update, context)

    update.message.reply_text.assert_awaited_with(
        "Minutes must be a positive whole number."
    )


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
