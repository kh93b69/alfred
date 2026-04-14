import json
import os
import logging
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Файл для хранения напоминаний (переживают перезапуск)
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reminders.json")

# Ссылки на scheduler, bot и owner — устанавливаются извне
_scheduler = None
_bot = None
_owner_chat_id = None


def init(scheduler, bot, owner_chat_id):
    """Инициализация модуля напоминаний"""
    global _scheduler, _bot, _owner_chat_id
    _scheduler = scheduler
    _bot = bot
    _owner_chat_id = owner_chat_id

    # Загружаем сохранённые напоминания
    _load_and_schedule()


def _ensure_data_dir():
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)


def _load_reminders() -> list[dict]:
    """Загружает напоминания из файла"""
    _ensure_data_dir()
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_reminders(reminders: list[dict]):
    """Сохраняет напоминания в файл"""
    _ensure_data_dir()
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


def _load_and_schedule():
    """Загружает напоминания и регистрирует их в планировщике"""
    reminders = _load_reminders()
    for r in reminders:
        _schedule_one(r)
    if reminders:
        logger.info(f"Загружено {len(reminders)} напоминаний")


async def _send_reminder(text: str):
    """Отправляет напоминание в Telegram"""
    if _bot and _owner_chat_id:
        await _bot.send_message(_owner_chat_id, f"🔔 **Напоминание:**\n{text}", parse_mode="Markdown")


def _schedule_one(reminder: dict):
    """Регистрирует одно напоминание в планировщике"""
    if not _scheduler:
        return

    job_id = f"reminder_{reminder['id']}"

    # Парсим время "HH:MM"
    hour, minute = map(int, reminder["time"].split(":"))

    # Дни недели: "daily" или "mon,tue,wed..."
    days = reminder.get("days", "daily")
    if days == "daily":
        trigger = CronTrigger(hour=hour, minute=minute)
    else:
        trigger = CronTrigger(hour=hour, minute=minute, day_of_week=days)

    _scheduler.add_job(
        _send_reminder,
        trigger,
        args=[reminder["text"]],
        id=job_id,
        replace_existing=True,
    )


def add_reminder(text: str, time: str, days: str = "daily") -> dict:
    """
    Добавляет напоминание.
    time: "HH:MM"
    days: "daily" или "mon,tue,wed,thu,fri,sat,sun"
    """
    reminders = _load_reminders()

    # Генерируем ID
    new_id = max([r["id"] for r in reminders], default=0) + 1

    reminder = {
        "id": new_id,
        "text": text,
        "time": time,
        "days": days,
        "created": datetime.now().isoformat(),
    }

    reminders.append(reminder)
    _save_reminders(reminders)
    _schedule_one(reminder)

    logger.info(f"Добавлено напоминание #{new_id}: {text} в {time}")
    return reminder


def remove_reminder(reminder_id: int) -> bool:
    """Удаляет напоминание по ID"""
    reminders = _load_reminders()
    new_list = [r for r in reminders if r["id"] != reminder_id]

    if len(new_list) == len(reminders):
        return False

    _save_reminders(new_list)

    # Убираем из планировщика
    job_id = f"reminder_{reminder_id}"
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass

    logger.info(f"Удалено напоминание #{reminder_id}")
    return True


def get_all() -> list[dict]:
    """Возвращает все напоминания"""
    return _load_reminders()
