# WhatsApp Checker Bot

Простой Telegram-бот, который позволяет проверять, есть ли WhatsApp у клиента из локальной базы данных.

## Возможности

- `/check <номер>` — узнать статус по номеру.
- `/set <номер> <да|нет> [примечание]` — добавить или обновить информацию.
- `/stats` — посмотреть количество записей и сколько из них с WhatsApp.

## Настройка окружения

1. Установите зависимости:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Создайте `.env` файл рядом со скриптом и добавьте токен Telegram-бота:

   ```env
   TELEGRAM_BOT_TOKEN=ваш_токен
   ```

   По умолчанию база создаётся по пути `data/contacts.db`. Можно переопределить переменной `WHATSAPP_DB`.

3. Запустите бота:

   ```bash
   python whatsapp_checker_bot.py
   ```

## Импорт существующей базы

Скрипт поддерживает импорт из CSV на уровне кода (метод `bulk_import`). Пример файла `sample_contacts.csv`:

```csv
phone,has_whatsapp,note
+79990000000,1,VIP клиент
+79990000001,0,Не отвечает
```

Можно использовать Python-консоль для загрузки:

```python
from whatsapp_checker_bot import WhatsAppDatabase, normalize_phone
from pathlib import Path

db = WhatsAppDatabase(Path("data/contacts.db"))
records = [
    (normalize_phone("+79990000000"), True, "VIP клиент"),
    (normalize_phone("+79990000001"), False, "Не отвечает"),
]
db.bulk_import(records)
```

После этого данные будут доступны команде `/check`.
