import json
import os
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

from bot.config import NOTION_API_KEY, NOTION_ROOT_PAGE_ID

logger = logging.getLogger(__name__)

# Локальный бэкап
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reminders.json")

# Кеш в памяти
_reminders_cache: list[dict] = []
_cache_loaded = False

# Глобальные зависимости (устанавливаются из main)
_scheduler = None
_bot = None
_owner_chat_id = None


def init(scheduler, bot, owner_chat_id):
    """Инициализация модуля"""
    global _scheduler, _bot, _owner_chat_id
    _scheduler = scheduler
    _bot = bot
    _owner_chat_id = owner_chat_id
    _load_and_schedule()


def _ensure_dir():
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)


def _find_reminders_page_id() -> str:
    """Находит страницу 'Напоминания' в Notion, создаёт если нет"""
    if not NOTION_API_KEY or not NOTION_ROOT_PAGE_ID:
        return ""

    try:
        from bot.services.notion import get_child_pages, _request

        # Ищем существующую страницу
        pages = get_child_pages(NOTION_ROOT_PAGE_ID)
        for p in pages:
            if p["title"] == "Напоминания":
                return p["id"]

        # Создаём
        result = _request("POST", "/pages", {
            "parent": {"page_id": NOTION_ROOT_PAGE_ID},
            "properties": {"title": [{"text": {"content": "Напоминания"}}]},
            "icon": {"type": "emoji", "emoji": "🔔"},
            "children": [],
        })
        logger.info("Создана страница 'Напоминания' в Notion")
        return result["id"]
    except Exception as e:
        logger.error(f"Ошибка поиска страницы напоминаний: {e}")
        return ""


def _load_from_notion() -> list[dict]:
    """Загружает напоминания из Notion"""
    page_id = _find_reminders_page_id()
    if not page_id:
        return []

    try:
        # Получаем блоки страницы
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
        req.add_header("Notion-Version", "2022-06-28")

        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Ищем блок с кодом — там хранится JSON
        for block in data.get("results", []):
            if block.get("type") == "code":
                code_data = block.get("code", {})
                rich_text = code_data.get("rich_text", [])
                text = "".join(t.get("plain_text", "") for t in rich_text)
                if text:
                    return json.loads(text)
        return []
    except Exception as e:
        logger.error(f"Ошибка загрузки из Notion: {e}")
        return []


def _save_to_notion(reminders: list[dict]):
    """Сохраняет напоминания в Notion как JSON блок"""
    page_id = _find_reminders_page_id()
    if not page_id:
        return

    try:
        from bot.services.notion import _request

        # Получаем существующие блоки
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
        req.add_header("Notion-Version", "2022-06-28")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Удаляем все существующие блоки
        for block in data.get("results", []):
            _request("DELETE", f"/blocks/{block['id']}")

        # Создаём новый блок с JSON
        json_str = json.dumps(reminders, ensure_ascii=False, indent=2)
        new_blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"Всего напоминаний: {len(reminders)}. Данные в JSON ниже (не редактировать вручную)."
                    }}]
                }
            },
            {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": json_str[:2000]}}],
                    "language": "json"
                }
            }
        ]

        # Читаемый список
        for r in reminders:
            days_label = "ежедневно" if r.get("days", "daily") == "daily" else r["days"]
            new_blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"#{r['id']} — {r['time']} ({days_label}): {r['text']}"
                    }}]
                }
            })

        _request("PATCH", f"/blocks/{page_id}/children", {"children": new_blocks[:100]})
        logger.info(f"Напоминания сохранены в Notion: {len(reminders)}")
    except Exception as e:
        logger.error(f"Ошибка сохранения в Notion: {e}")


def _load_from_file() -> list[dict]:
    """Фолбэк: загрузка из локального файла"""
    _ensure_dir()
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_to_file(reminders: list[dict]):
    """Фолбэк: сохранение в локальный файл"""
    _ensure_dir()
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка записи файла: {e}")


def _load_reminders() -> list[dict]:
    """Загружает напоминания — сначала Notion, потом файл"""
    global _cache_loaded, _reminders_cache

    if _cache_loaded:
        return _reminders_cache

    # Пробуем Notion
    reminders = _load_from_notion()

    # Если в Notion пусто — пробуем файл
    if not reminders:
        reminders = _load_from_file()
        # Если нашли в файле — переносим в Notion
        if reminders:
            _save_to_notion(reminders)

    _reminders_cache = reminders
    _cache_loaded = True
    return reminders


def _save_reminders(reminders: list[dict]):
    """Сохраняет в Notion + файл"""
    global _reminders_cache
    _reminders_cache = reminders

    _save_to_notion(reminders)
    _save_to_file(reminders)


async def _send_reminder(text: str):
    """Отправляет напоминание в Telegram"""
    if _bot and _owner_chat_id:
        try:
            await _bot.send_message(_owner_chat_id, f"🔔 **Напоминание:**\n{text}", parse_mode="Markdown")
            logger.info(f"Отправлено напоминание: {text[:50]}")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")


def _schedule_one(reminder: dict):
    """Регистрирует напоминание в планировщике"""
    if not _scheduler:
        return

    job_id = f"reminder_{reminder['id']}"

    try:
        hour, minute = map(int, reminder["time"].split(":"))
    except Exception:
        logger.error(f"Неверный формат времени: {reminder.get('time')}")
        return

    days = reminder.get("days", "daily")

    # Используем часовой пояс владельца
    from datetime import timezone, timedelta
    owner_tz = timezone(timedelta(hours=5))

    if days == "daily":
        trigger = CronTrigger(hour=hour, minute=minute, timezone=owner_tz)
    else:
        trigger = CronTrigger(hour=hour, minute=minute, day_of_week=days, timezone=owner_tz)

    _scheduler.add_job(
        _send_reminder,
        trigger,
        args=[reminder["text"]],
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"Зарегистрировано напоминание #{reminder['id']}: {reminder['time']} {days}")


def _load_and_schedule():
    """Загружает и регистрирует все напоминания"""
    reminders = _load_reminders()
    for r in reminders:
        _schedule_one(r)
    logger.info(f"Загружено {len(reminders)} напоминаний")


def add_reminder(text: str, time: str, days: str = "daily") -> dict:
    """Добавляет напоминание"""
    reminders = _load_reminders()
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

    logger.info(f"Добавлено напоминание #{new_id}: {text} в {time} ({days})")
    return reminder


def remove_reminder(reminder_id: int) -> bool:
    """Удаляет напоминание"""
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
