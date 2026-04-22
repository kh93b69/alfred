import json
import os
import logging
from datetime import datetime

from bot.config import NOTION_API_KEY, NOTION_ROOT_PAGE_ID

logger = logging.getLogger(__name__)

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "task_memory.json")

# Кеш
_memory: dict = {"rejected": [], "completed": [], "proposed": []}
_loaded = False


def _ensure_dir():
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)


def _find_memory_page_id() -> str:
    """Находит страницу 'История задач' в Notion"""
    if not NOTION_API_KEY or not NOTION_ROOT_PAGE_ID:
        return ""
    try:
        from bot.services.notion import get_child_pages, _request
        pages = get_child_pages(NOTION_ROOT_PAGE_ID)
        for p in pages:
            if p["title"] == "История задач":
                return p["id"]
        result = _request("POST", "/pages", {
            "parent": {"page_id": NOTION_ROOT_PAGE_ID},
            "properties": {"title": [{"text": {"content": "История задач"}}]},
            "icon": {"type": "emoji", "emoji": "📜"},
            "children": [],
        })
        return result["id"]
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return ""


def _load_from_notion() -> dict:
    """Загружает историю из Notion"""
    page_id = _find_memory_page_id()
    if not page_id:
        return {}
    try:
        import urllib.request
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
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки истории: {e}")
        return {}


def _save_to_notion(memory: dict):
    """Сохраняет историю в Notion"""
    page_id = _find_memory_page_id()
    if not page_id:
        return
    try:
        from bot.services.notion import _request
        import urllib.request

        # Удаляем старые блоки
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
        req.add_header("Notion-Version", "2022-06-28")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for block in data.get("results", []):
            _request("DELETE", f"/blocks/{block['id']}")

        json_str = json.dumps(memory, ensure_ascii=False, indent=2)
        blocks = [
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
        for key in ["rejected", "completed"]:
            items = memory.get(key, [])
            if items:
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": f"{key} ({len(items)})"}}]
                    }
                })
                for item in items[-20:]:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {
                                "content": f"{item.get('date', '')}: {item.get('name', '')}"
                            }}]
                        }
                    })

        _request("PATCH", f"/blocks/{page_id}/children", {"children": blocks[:100]})
    except Exception as e:
        logger.error(f"Ошибка сохранения истории: {e}")


def _load() -> dict:
    """Загружает память"""
    global _memory, _loaded
    if _loaded:
        return _memory

    # Пробуем Notion
    notion_data = _load_from_notion()
    if notion_data:
        _memory = notion_data
    else:
        # Фолбэк файл
        _ensure_dir()
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    _memory = json.load(f)
            except Exception:
                pass

    # Гарантируем структуру
    for key in ["rejected", "completed", "proposed"]:
        if key not in _memory:
            _memory[key] = []

    _loaded = True
    return _memory


def _save():
    """Сохраняет память в Notion + файл"""
    _save_to_notion(_memory)
    _ensure_dir()
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка записи файла: {e}")


def add_proposed(name: str):
    """Записывает что задача была предложена"""
    memory = _load()
    memory["proposed"].append({
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    # Храним последние 200
    memory["proposed"] = memory["proposed"][-200:]
    _save()


def add_rejected(name: str):
    """Записывает отклонённую задачу"""
    memory = _load()
    memory["rejected"].append({
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    memory["rejected"] = memory["rejected"][-200:]
    _save()


def add_completed(name: str):
    """Записывает выполненную задачу"""
    memory = _load()
    memory["completed"].append({
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    memory["completed"] = memory["completed"][-200:]
    _save()


def get_history_summary() -> str:
    """Краткая история для промпта"""
    memory = _load()
    parts = []

    rejected = memory.get("rejected", [])
    if rejected:
        parts.append("ОТКЛОНЁННЫЕ задачи (НЕ предлагать снова):")
        for item in rejected[-30:]:
            parts.append(f"  - {item['name']}")

    completed = memory.get("completed", [])
    if completed:
        parts.append("\nВЫПОЛНЕННЫЕ задачи (НЕ дублировать):")
        for item in completed[-20:]:
            parts.append(f"  - {item['name']}")

    proposed = memory.get("proposed", [])
    if proposed:
        today = datetime.now().strftime("%Y-%m-%d")
        today_proposed = [p for p in proposed if p.get("date") == today]
        if today_proposed:
            parts.append("\nСЕГОДНЯ уже предлагались:")
            for item in today_proposed:
                parts.append(f"  - {item['name']}")

    return "\n".join(parts) if parts else ""
