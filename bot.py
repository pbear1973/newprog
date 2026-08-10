"""Telegram bot that responds to /time, /quote, and /beep."""

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


def _is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return whether the sender may use restricted commands."""
    allow = context.application.bot_data.get("allowed_user_ids") or set()
    if not allow:
        return True
    if update.effective_user is None:
        return False
    return update.effective_user.id in allow


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /time — reply with the host system clock."""
    if update.effective_user is None or update.message is None:
        return

    if not _is_authorized(update, context):
        logger.warning(
            "Ignoring /time from unauthorized user %s",
            update.effective_user.id,
        )
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(format_system_time())


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quote — reply with a randomly chosen quote."""
    if update.effective_user is None or update.message is None:
        return

    if not _is_authorized(update, context):
        logger.warning(
            "Ignoring /quote from unauthorized user %s",
            update.effective_user.id,
        )
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(random_quote())


async def beep_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /beep — reply with BEEP!"""
    if update.effective_user is None or update.message is None:
        return

    if not _is_authorized(update, context):
        logger.warning(
            "Ignoring /beep from unauthorized user %s",
            update.effective_user.id,
        )
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text("BEEP!")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a short usage note."""
    if update.message is None:
        return
    await update.message.reply_text(
        "Send /time for the system time, /quote for a random quote, or /beep."
    )


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["allowed_user_ids"] = allowed_user_ids()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("beep", beep_command))
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
