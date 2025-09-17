"""Simple Telegram bot to check whether numbers are marked as having WhatsApp."""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Updater


LOGGER = logging.getLogger(__name__)


class WhatsAppDatabase:
    """Wrapper around a SQLite database with helper methods for contacts."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    phone TEXT PRIMARY KEY,
                    has_whatsapp INTEGER NOT NULL,
                    note TEXT DEFAULT ''
                )
                """
            )

    def get_contact(self, phone: str) -> Optional[tuple[str, bool, str]]:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT phone, has_whatsapp, note FROM contacts WHERE phone = ?",
                (phone,),
            ).fetchone()
        if not row:
            return None
        return row[0], bool(row[1]), row[2]

    def upsert_contact(self, phone: str, has_whatsapp: bool, note: str = "") -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO contacts(phone, has_whatsapp, note)
                VALUES(:phone, :has_whatsapp, :note)
                ON CONFLICT(phone) DO UPDATE SET
                    has_whatsapp = excluded.has_whatsapp,
                    note = excluded.note
                """,
                {
                    "phone": phone,
                    "has_whatsapp": int(has_whatsapp),
                    "note": note,
                },
            )

    def get_stats(self) -> tuple[int, int]:
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                "SELECT has_whatsapp, COUNT(*) FROM contacts GROUP BY has_whatsapp"
            ).fetchall()
        total = sum(count for _, count in rows)
        positive = sum(count for status, count in rows if status == 1)
        return total, positive

    def bulk_import(self, records: Iterable[tuple[str, bool, str]]) -> int:
        with sqlite3.connect(self._path) as conn:
            conn.executemany(
                """
                INSERT INTO contacts(phone, has_whatsapp, note)
                VALUES(:phone, :has_whatsapp, :note)
                ON CONFLICT(phone) DO UPDATE SET
                    has_whatsapp = excluded.has_whatsapp,
                    note = excluded.note
                """,
                (
                    {
                        "phone": phone,
                        "has_whatsapp": int(has_whatsapp),
                        "note": note,
                    }
                    for phone, has_whatsapp, note in records
                ),
            )
            return conn.total_changes


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("Телефон должен содержать цифры")
    if raw.strip().startswith("+"):
        return "+" + digits
    return digits


def parse_status(status_raw: str) -> bool:
    normalized = status_raw.strip().lower()
    if normalized in {"1", "да", "y", "yes", "true", "есть"}:
        return True
    if normalized in {"0", "нет", "n", "no", "false", "none"}:
        return False
    raise ValueError(
        "Статус должен быть 'да'/'нет', '1'/'0', 'yes'/'no' или 'true'/'false'"
    )


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Привет! Отправь /check <номер> чтобы узнать, есть ли WhatsApp у контакта.\n"
        "Можно добавить или обновить данные командой /set <номер> <да|нет> [примечание]."
    )


def check_command(update: Update, context: CallbackContext, db: WhatsAppDatabase) -> None:
    if not context.args:
        update.message.reply_text("Укажи номер телефона после команды. Пример: /check +79990001122")
        return
    try:
        phone = normalize_phone(context.args[0])
    except ValueError as exc:
        update.message.reply_text(f"Ошибка: {exc}")
        return
    contact = db.get_contact(phone)
    if not contact:
        update.message.reply_text(
            "Нет данных по этому номеру. Добавь информацию командой /set <номер> <да|нет>."
        )
        return
    _, has_whatsapp, note = contact
    status = "есть" if has_whatsapp else "нет"
    note_text = f"\nПримечание: {note}" if note else ""
    update.message.reply_text(f"У номера {phone} {status} WhatsApp.{note_text}")


def set_command(update: Update, context: CallbackContext, db: WhatsAppDatabase) -> None:
    if len(context.args) < 2:
        update.message.reply_text(
            "Использование: /set <номер> <да|нет> [примечание]. Пример: /set +79990001122 да Клиент"
        )
        return
    try:
        phone = normalize_phone(context.args[0])
        status = parse_status(context.args[1])
    except ValueError as exc:
        update.message.reply_text(f"Ошибка: {exc}")
        return
    note = " ".join(context.args[2:]).strip()
    db.upsert_contact(phone, status, note)
    update.message.reply_text(
        f"Информация сохранена: {phone} -> {'есть' if status else 'нет'} WhatsApp"
        + (f" ({note})" if note else "")
    )


def stats_command(update: Update, context: CallbackContext, db: WhatsAppDatabase) -> None:
    total, positive = db.get_stats()
    if total == 0:
        update.message.reply_text("База пока пуста. Добавь контакты через /set.")
        return
    update.message.reply_text(
        f"В базе {total} контактов. WhatsApp найден у {positive}."
    )


def create_updater(token: str, db: WhatsAppDatabase) -> Updater:
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("check", lambda u, c: check_command(u, c, db)))
    dispatcher.add_handler(CommandHandler("set", lambda u, c: set_command(u, c, db)))
    dispatcher.add_handler(CommandHandler("stats", lambda u, c: stats_command(u, c, db)))

    return updater


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Переменная окружения TELEGRAM_BOT_TOKEN не установлена. "
            "Создайте .env файл или передайте токен при запуске."
        )

    db_path = Path(
        os.getenv(
            "WHATSAPP_DB",
            Path(__file__).resolve().parent / "data" / "contacts.db",
        )
    )
    db = WhatsAppDatabase(db_path)

    updater = create_updater(token, db)
    LOGGER.info("Запуск бота. Нажмите Ctrl+C для остановки.")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
