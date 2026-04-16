import os
import json
import logging
import urllib.request

from bot.config import NOTION_API_KEY, NOTION_ROOT_PAGE_ID

logger = logging.getLogger(__name__)

# Папка с файлами базы знаний (локальный фолбэк)
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge")

# Кеш базы знаний в памяти: {название: текст}
_knowledge_cache: dict[str, str] = {}
_cache_loaded = False


def _load_from_local():
    """Загружает из локальных файлов (фолбэк)"""
    if not os.path.exists(KNOWLEDGE_DIR):
        return

    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not filename.endswith((".txt", ".md")):
            continue

        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    name = filename.rsplit(".", 1)[0]
                    _knowledge_cache[name] = content
        except Exception as e:
            logger.error(f"Ошибка чтения {filename}: {e}")


def _load_from_notion():
    """Загружает базу знаний из Notion (раздел 'База знаний')"""
    if not NOTION_API_KEY or not NOTION_ROOT_PAGE_ID:
        return

    try:
        from bot.services.notion import ensure_sections, get_child_pages

        sections = ensure_sections()
        kb_page_id = sections.get("База знаний")
        if not kb_page_id:
            return

        # Получаем страницы в разделе "База знаний"
        pages = get_child_pages(kb_page_id)

        for page in pages:
            title = page["title"]
            page_id = page["id"]

            # Загружаем контент страницы
            content = _fetch_page_content(page_id)
            if content:
                _knowledge_cache[title] = content
                logger.info(f"Загружено из Notion: {title}")

    except Exception as e:
        logger.error(f"Ошибка загрузки из Notion: {e}")


def _fetch_page_content(page_id: str) -> str:
    """Загружает текстовый контент страницы Notion"""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", "2022-06-28")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""

    lines = []
    for block in data.get("results", []):
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])

        text = "".join(t.get("plain_text", "") for t in rich_text)

        if block_type == "heading_1":
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            lines.append(f"### {text}")
        elif block_type == "bulleted_list_item":
            lines.append(f"- {text}")
        elif block_type == "numbered_list_item":
            lines.append(f"1. {text}")
        elif text:
            lines.append(text)

    return "\n".join(lines)


def _ensure_loaded():
    """Загружает базу знаний если ещё не загружена"""
    global _cache_loaded
    if _cache_loaded:
        return

    # Сначала локальные файлы
    _load_from_local()

    # Потом Notion (перезаписывает если есть совпадения)
    _load_from_notion()

    _cache_loaded = True
    logger.info(f"База знаний загружена: {len(_knowledge_cache)} документов")


def load_knowledge() -> str:
    """Загружает всю базу знаний в одну строку для промпта"""
    _ensure_loaded()

    if not _knowledge_cache:
        return ""

    parts = [f"## {name}\n{content}" for name, content in _knowledge_cache.items()]
    return "\n\n---\n\n".join(parts)


def add_note(title: str, content: str) -> str:
    """Добавляет заметку в базу знаний (Notion + локальный кеш)"""
    # Сохраняем в кеш
    _knowledge_cache[title] = content

    # Сохраняем в Notion если подключён
    if NOTION_API_KEY:
        try:
            from bot.services.notion import add_to_section
            add_to_section("База знаний", title, content, icon="📄")
            logger.info(f"Заметка сохранена в Notion: {title}")
        except Exception as e:
            logger.error(f"Ошибка сохранения в Notion: {e}")

    # Сохраняем локально как фолбэк
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    safe_title = safe_title.strip().replace(" ", "_")
    filename = f"{safe_title}.txt"
    filepath = os.path.join(KNOWLEDGE_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


def add_to_cache(title: str, content: str):
    """Добавляет в кеш без сохранения в файл (для загруженных файлов)"""
    _knowledge_cache[title] = content

    # Сохраняем в Notion
    if NOTION_API_KEY:
        try:
            from bot.services.notion import add_to_section
            add_to_section("База знаний", title, content, icon="📄")
            logger.info(f"Файл сохранён в Notion: {title}")
        except Exception as e:
            logger.error(f"Ошибка Notion: {e}")


def list_files() -> list[str]:
    """Возвращает список документов в базе знаний"""
    _ensure_loaded()
    return sorted(_knowledge_cache.keys())


def reload():
    """Принудительная перезагрузка базы знаний"""
    global _cache_loaded
    _knowledge_cache.clear()
    _cache_loaded = False
    _ensure_loaded()
