"""Telegram bot that responds to /time, /quote, /beep, /bug, /config, /stop, and /help."""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Default how often /bug sends "Hello!" (minutes / seconds). Overridable via /config.
DEFAULT_BUG_INTERVAL_MINUTES = 10
BUG_INTERVAL_SECONDS = DEFAULT_BUG_INTERVAL_MINUTES * 60
BUG_INTERVAL_KEY = "bug_interval_seconds"
# Minimum / maximum minutes accepted by /config.
MIN_BUG_INTERVAL_MINUTES = 1
MAX_BUG_INTERVAL_MINUTES = 24 * 60

# Command catalog used by /help (and mirrored in /start).
COMMANDS: list[tuple[str, str]] = [
    ("/start", "Show a short welcome message and point you to /help."),
    ("/help", "List all bot commands and a short explanation for each."),
    ("/time", "Show the host system clock in UTC and local time."),
    ("/quote", "Reply with a randomly chosen famous quote."),
    ("/beep", "Reply with BEEP!"),
    ("/bug", 'Start sending "Hello!" on the configured interval in this chat.'),
    (
        "/config",
        "Set or show the /bug Hello! interval in minutes. Usage: /config <minutes>.",
    ),
    ("/stop", "Stop the recurring /bug Hello! messages in this chat."),
]

# Famous quotes collected from public internet sources (verified attributions).
QUOTES: list[tuple[str, str]] = [
    (
        "Start where you are. Use what you have. Do what you can.",
        "Arthur Ashe",
    ),
    (
        "You don't have to be great to start, but you have to start to be great.",
        "Zig Ziglar",
    ),
    (
        "It always seems impossible until it's done.",
        "Nelson Mandela",
    ),
    (
        "Believe you can and you're halfway there.",
        "Theodore Roosevelt",
    ),
    (
        "The only thing we have to fear is fear itself.",
        "Franklin D. Roosevelt",
    ),
    (
        "Injustice anywhere is a threat to justice everywhere.",
        "Martin Luther King Jr.",
    ),
    (
        "If I have seen further it is by standing on the shoulders of giants.",
        "Isaac Newton",
    ),
    (
        "Whether you think you can or you think you can't, you're right.",
        "Henry Ford",
    ),
    (
        "I have not failed. I've just found 10,000 ways that won't work.",
        "Thomas Edison",
    ),
    (
        "Your time is limited, so don't waste it living someone else's life.",
        "Steve Jobs",
    ),
]


def format_system_time(now: datetime | None = None) -> str:
    """Return a human-readable UTC and local system time string."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    utc = now.astimezone(timezone.utc)
    local = now.astimezone()
    return (
        f"System time (UTC): {utc.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"System time (local): {local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )


def format_quote(text: str, author: str) -> str:
    """Return a human-readable quote string."""
    return f'"{text}"\n— {author}'


def format_help() -> str:
    """Return a human-readable list of all bot commands."""
    lines = ["Available commands:", ""]
    for name, description in COMMANDS:
        lines.append(f"{name} — {description}")
    return "\n".join(lines)


def random_quote(rng: random.Random | None = None) -> str:
    """Pick a random quote from the built-in list and format it."""
    picker = rng if rng is not None else random
    text, author = picker.choice(QUOTES)
    return format_quote(text, author)


def allowed_user_ids() -> set[int]:
    """Parse optional comma-separated TELEGRAM_ALLOWED_USER_ID allow-list."""
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return ids


def bug_job_name(chat_id: int) -> str:
    """Stable job name for the /bug interval in a given chat."""
    return f"bug-hello-{chat_id}"


def format_minutes(minutes: int) -> str:
    """Return a short human-readable minutes phrase."""
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


def get_bug_interval_seconds(bot_data: dict) -> int:
    """Return the configured /bug interval in seconds (default 10 minutes)."""
    value = bot_data.get(BUG_INTERVAL_KEY, BUG_INTERVAL_SECONDS)
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return BUG_INTERVAL_SECONDS
    return seconds if seconds > 0 else BUG_INTERVAL_SECONDS


def get_bug_interval_minutes(bot_data: dict) -> int:
    """Return the configured /bug interval in whole minutes."""
    return max(1, get_bug_interval_seconds(bot_data) // 60)


def set_bug_interval_minutes(bot_data: dict, minutes: int) -> int:
    """Store a new /bug interval (minutes) and return the stored value."""
    if minutes < MIN_BUG_INTERVAL_MINUTES or minutes > MAX_BUG_INTERVAL_MINUTES:
        raise ValueError(
            f"Interval must be between {MIN_BUG_INTERVAL_MINUTES} and "
            f"{MAX_BUG_INTERVAL_MINUTES} minutes."
        )
    bot_data[BUG_INTERVAL_KEY] = minutes * 60
    return minutes


def parse_config_minutes(args: list[str] | None) -> int | None:
    """
    Parse /config arguments.

    Returns None when no minutes were provided (show current).
    Raises ValueError for invalid input.
    """
    if not args:
        return None
    if len(args) != 1:
        raise ValueError("Usage: /config <minutes>")
    raw = args[0].strip()
    if not raw.isdigit():
        raise ValueError("Minutes must be a positive whole number.")
    minutes = int(raw)
    if minutes < MIN_BUG_INTERVAL_MINUTES or minutes > MAX_BUG_INTERVAL_MINUTES:
        raise ValueError(
            f"Interval must be between {MIN_BUG_INTERVAL_MINUTES} and "
            f"{MAX_BUG_INTERVAL_MINUTES} minutes."
        )
    return minutes


def _is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return whether the sender may use restricted commands."""
    allow = context.application.bot_data.get("allowed_user_ids") or set()
    if not allow:
        return True
    if update.effective_user is None:
        return False
    return update.effective_user.id in allow


async def _require_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Authorize the sender or reply Unauthorized. Return True when allowed."""
    if update.effective_user is None or update.message is None:
        return False
    if _is_authorized(update, context):
        return True
    logger.warning(
        "Ignoring command from unauthorized user %s",
        update.effective_user.id,
    )
    await update.message.reply_text("Unauthorized.")
    return False


async def send_bug_hello(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback: send Hello! to the chat that started /bug."""
    chat_id = context.job.chat_id if context.job else None
    if chat_id is None:
        return
    await context.bot.send_message(chat_id=chat_id, text="Hello!")


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /time — reply with the host system clock."""
    if not await _require_authorized(update, context):
        return
    await update.message.reply_text(format_system_time())


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quote — reply with a randomly chosen quote."""
    if not await _require_authorized(update, context):
        return
    await update.message.reply_text(random_quote())


async def beep_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /beep — reply with BEEP!"""
    if not await _require_authorized(update, context):
        return
    await update.message.reply_text("BEEP!")


def _schedule_bug_job(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """(Re)schedule the /bug Hello! job for a chat. Returns interval seconds."""
    job_queue = context.application.job_queue
    interval = get_bug_interval_seconds(context.application.bot_data)
    name = bug_job_name(chat_id)
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    job_queue.run_repeating(
        send_bug_hello,
        interval=interval,
        first=interval,
        chat_id=chat_id,
        name=name,
    )
    return interval


async def bug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bug — start sending Hello! on the configured interval in this chat."""
    if not await _require_authorized(update, context):
        return

    chat = update.effective_chat
    if chat is None or update.message is None:
        return

    job_queue = context.application.job_queue
    if job_queue is None:
        await update.message.reply_text(
            "Repeating jobs are unavailable (job-queue not installed)."
        )
        return

    interval = _schedule_bug_job(context, chat.id)
    minutes = max(1, interval // 60)
    await update.message.reply_text(
        f'Bug mode on. I will send "Hello!" every {format_minutes(minutes)}. '
        "Use /stop to cancel."
    )


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /config — set or show the /bug Hello! interval in minutes."""
    if not await _require_authorized(update, context):
        return
    if update.message is None:
        return

    try:
        minutes = parse_config_minutes(context.args)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    if minutes is None:
        current = get_bug_interval_minutes(context.application.bot_data)
        await update.message.reply_text(
            f"Bug interval is {format_minutes(current)}. "
            "Usage: /config <minutes>"
        )
        return

    set_bug_interval_minutes(context.application.bot_data, minutes)

    # If bug mode is already running in this chat, apply the new interval now.
    chat = update.effective_chat
    job_queue = context.application.job_queue
    rescheduled = False
    if chat is not None and job_queue is not None:
        name = bug_job_name(chat.id)
        if job_queue.get_jobs_by_name(name):
            _schedule_bug_job(context, chat.id)
            rescheduled = True

    message = f"Bug interval set to {format_minutes(minutes)}."
    if rescheduled:
        message += " Active /bug timer updated."
    await update.message.reply_text(message)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop — stop /bug Hello! interval for this chat."""
    if not await _require_authorized(update, context):
        return

    chat = update.effective_chat
    if chat is None or update.message is None:
        return

    job_queue = context.application.job_queue
    if job_queue is None:
        await update.message.reply_text(
            "Repeating jobs are unavailable (job-queue not installed)."
        )
        return

    name = bug_job_name(chat.id)
    jobs = job_queue.get_jobs_by_name(name)
    if not jobs:
        await update.message.reply_text("No active /bug timer in this chat.")
        return

    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("Stopped the /bug Hello! messages.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a short usage note."""
    if update.message is None:
        return
    await update.message.reply_text(
        "Welcome. Send /help to list all commands, or try /time, /quote, /beep, "
        "/bug, or /config."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — list and explain all commands."""
    if update.message is None:
        return
    await update.message.reply_text(format_help())


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["allowed_user_ids"] = allowed_user_ids()
    app.bot_data[BUG_INTERVAL_KEY] = BUG_INTERVAL_SECONDS
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("beep", beep_command))
    app.add_handler(CommandHandler("bug", bug_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("stop", stop_command))
    return app


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is required")
        sys.exit(1)

    app = build_application(token)
    logger.info("Starting bot (allowed users: %s)", app.bot_data["allowed_user_ids"] or "any")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
