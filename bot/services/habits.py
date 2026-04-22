import json
import os
import logging
import urllib.request
from datetime import datetime

from bot.config import NOTION_API_KEY, NOTION_ROOT_PAGE_ID

logger = logging.getLogger(__name__)

HABITS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "habits.json")

# Структура:
# {"habits": [{"id": 1, "name": "Пить витамины", "time": "09:00", "created": "..."}],
#  "checkins": [{"habit_id": 1, "date": "2026-04-16", "done": true}]}
_data: dict = {"habits": [], "checkins": []}
_loaded = False


def _ensure_dir():
    os.makedirs(os.path.dirname(HABITS_FILE), exist_ok=True)


def _find_page_id() -> str:
    """Находит страницу 'Привычки' в Notion"""
    if not NOTION_API_KEY or not NOTION_ROOT_PAGE_ID:
        return ""
    try:
        from bot.services.notion import get_child_pages, _request
        pages = get_child_pages(NOTION_ROOT_PAGE_ID)
        for p in pages:
            if p["title"] == "Привычки":
                return p["id"]
        result = _request("POST", "/pages", {
            "parent": {"page_id": NOTION_ROOT_PAGE_ID},
            "properties": {"title": [{"text": {"content": "Привычки"}}]},
            "icon": {"type": "emoji", "emoji": "🌱"},
            "children": [],
        })
        return result["id"]
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return ""


def _load_from_notion() -> dict:
    page_id = _find_page_id()
    if not page_id:
        return {}
    try:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
        req.add_header("Notion-Version", "2022-06-28")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for block in data.get("results", []):
            if block.get("type") == "code":
                text = "".join(
                    t.get("plain_text", "")
                    for t in block.get("code", {}).get("rich_text", [])
                )
                if text:
                    return json.loads(text)
    except Exception as e:
        logger.error(f"Ошибка Notion: {e}")
    return {}


def _save_to_notion():
    page_id = _find_page_id()
    if not page_id:
        return
    try:
        from bot.services.notion import _request
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
        req.add_header("Notion-Version", "2022-06-28")
        with urllib.request.urlopen(req) as resp:
            existing = json.loads(resp.read().decode("utf-8"))
        for block in existing.get("results", []):
            _request("DELETE", f"/blocks/{block['id']}")

        json_str = json.dumps(_data, ensure_ascii=False, indent=2)
        blocks = [
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Привычки"}}]}
            }
        ]

        for h in _data.get("habits", []):
            # Статистика за 30 дней
            streak = get_streak(h["id"])
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"{h['name']} — {h.get('time', '09:00')} — streak: {streak} дней"
                    }}]
                }
            })

        blocks.append({
            "object": "block", "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": json_str[:2000]}}],
                "language": "json"
            }
        })

        _request("PATCH", f"/blocks/{page_id}/children", {"children": blocks[:100]})
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")


def _load():
    global _data, _loaded
    if _loaded:
        return _data

    notion_data = _load_from_notion()
    if notion_data and notion_data.get("habits"):
        _data = notion_data
    else:
        _ensure_dir()
        if os.path.exists(HABITS_FILE):
            try:
                with open(HABITS_FILE, "r", encoding="utf-8") as f:
                    _data = json.load(f)
            except Exception:
                pass

    # Структура
    if "habits" not in _data:
        _data["habits"] = []
    if "checkins" not in _data:
        _data["checkins"] = []

    _loaded = True
    return _data


def _save():
    _ensure_dir()
    try:
        with open(HABITS_FILE, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    _save_to_notion()


def add_habit(name: str, time: str = "09:00") -> dict:
    data = _load()
    new_id = max([h["id"] for h in data["habits"]], default=0) + 1
    habit = {
        "id": new_id,
        "name": name,
        "time": time,
        "created": datetime.now().isoformat(),
    }
    data["habits"].append(habit)
    _save()
    return habit


def remove_habit(habit_id: int) -> bool:
    data = _load()
    before = len(data["habits"])
    data["habits"] = [h for h in data["habits"] if h["id"] != habit_id]
    if len(data["habits"]) < before:
        _save()
        return True
    return False


def get_habits() -> list[dict]:
    return _load().get("habits", [])


def check_habit(habit_id: int, done: bool = True):
    """Отметка о выполнении привычки на сегодня"""
    data = _load()
    today = datetime.now().strftime("%Y-%m-%d")

    # Проверяем, не отмечено ли уже
    for checkin in data["checkins"]:
        if checkin["habit_id"] == habit_id and checkin["date"] == today:
            checkin["done"] = done
            _save()
            return

    data["checkins"].append({
        "habit_id": habit_id,
        "date": today,
        "done": done,
    })
    _save()


def get_streak(habit_id: int) -> int:
    """Возвращает текущий streak (дней подряд выполнено)"""
    data = _load()
    checkins = [
        c for c in data["checkins"]
        if c["habit_id"] == habit_id and c["done"]
    ]
    if not checkins:
        return 0

    # Сортируем по датам по убыванию
    dates = sorted(set(c["date"] for c in checkins), reverse=True)

    streak = 0
    today = datetime.now().date()
    for i, date_str in enumerate(dates):
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        expected = today.fromordinal(today.toordinal() - i)
        # Разрешаем пропуск сегодняшнего дня
        if i == 0 and (today - date).days > 1:
            break
        if date == expected or (i == 0 and (today - date).days <= 1):
            streak += 1
        else:
            break
    return streak


def get_stats(habit_id: int, days: int = 30) -> dict:
    """Статистика по привычке за N дней"""
    data = _load()
    checkins = [
        c for c in data["checkins"]
        if c["habit_id"] == habit_id and c["done"]
    ]

    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [c for c in checkins if c["date"] >= cutoff]

    return {
        "streak": get_streak(habit_id),
        "total_days": len(set(c["date"] for c in recent)),
        "period_days": days,
    }
