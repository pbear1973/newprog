"""Telegram bot that responds to /time with the system time."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /time — reply with the host system clock."""
    if update.effective_user is None or update.message is None:
        return

    allow = context.application.bot_data.get("allowed_user_ids") or set()
    if allow and update.effective_user.id not in allow:
        logger.warning(
            "Ignoring /time from unauthorized user %s",
            update.effective_user.id,
        )
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(format_system_time())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a short usage note."""
    if update.message is None:
        return
    await update.message.reply_text("Send /time to get the system time.")


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["allowed_user_ids"] = allowed_user_ids()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("time", time_command))
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
