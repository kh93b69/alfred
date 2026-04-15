import json
import logging
import urllib.request
import urllib.parse

from bot.config import NOTION_API_KEY, NOTION_ROOT_PAGE_ID

logger = logging.getLogger(__name__)

BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _request(method: str, path: str, body: dict = None) -> dict:
    """Выполняет запрос к Notion API"""
    url = f"{BASE_URL}{path}"

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def _text_to_blocks(text: str) -> list[dict]:
    """Конвертирует текст в блоки Notion"""
    blocks = []
    for line in text.split("\n"):
        line = line.rstrip()

        if not line:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}})
        elif line.startswith("### "):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}
            })
        elif line.startswith("## "):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}
            })
        elif line.startswith("# "):
            blocks.append({
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
            })
        elif line.startswith("- ") or line.startswith("• "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
            })
        elif len(line) > 1 and line[0].isdigit() and line[1] in ".)":
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]}
            })
        else:
            # Notion ограничивает блок 2000 символами
            chunks = [line[i:i+2000] for i in range(0, len(line), 2000)]
            for chunk in chunks:
                blocks.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
                })

    return blocks


def create_page(title: str, content: str, parent_page_id: str = None, icon: str = None) -> dict:
    """
    Создаёт страницу в Notion.
    Возвращает dict с id и url.
    """
    if parent_page_id is None:
        parent_page_id = NOTION_ROOT_PAGE_ID

    # Формируем блоки контента
    blocks = _text_to_blocks(content)

    body = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": [{"text": {"content": title}}]
        },
        "children": blocks[:100],  # Notion ограничивает 100 блоков за раз
    }

    if icon:
        body["icon"] = {"type": "emoji", "emoji": icon}

    result = _request("POST", "/pages", body)
    page_url = result.get("url", "")

    logger.info(f"Создана страница в Notion: {title} ({page_url})")

    # Если больше 100 блоков — добавляем остальные
    if len(blocks) > 100:
        page_id = result["id"]
        for i in range(100, len(blocks), 100):
            chunk = blocks[i:i+100]
            _request("PATCH", f"/blocks/{page_id}/children", {"children": chunk})

    return {"id": result["id"], "url": page_url, "title": title}


def create_section(title: str, icon: str = None) -> dict:
    """Создаёт раздел (пустую страницу) в корневой странице Notion"""
    body = {
        "parent": {"page_id": NOTION_ROOT_PAGE_ID},
        "properties": {
            "title": [{"text": {"content": title}}]
        },
        "children": [],
    }
    if icon:
        body["icon"] = {"type": "emoji", "emoji": icon}

    result = _request("POST", "/pages", body)
    logger.info(f"Создан раздел: {title}")
    return {"id": result["id"], "url": result.get("url", ""), "title": title}


def get_child_pages(page_id: str = None) -> list[dict]:
    """Получает дочерние страницы"""
    if page_id is None:
        page_id = NOTION_ROOT_PAGE_ID

    result = _request("GET", f"/blocks/{page_id}/children")
    pages = []
    for block in result.get("results", []):
        if block["type"] == "child_page":
            pages.append({
                "id": block["id"],
                "title": block["child_page"]["title"],
            })
    return pages


# ID разделов в Notion (кешируются после первого создания)
_sections: dict[str, str] = {}

SECTION_STRUCTURE = {
    "Регламенты": "📋",
    "База знаний": "🧠",
    "Саммари": "📖",
    "Контакты": "👥",
    "Идеи": "💡",
    "Цели": "🎯",
}


def ensure_sections() -> dict[str, str]:
    """
    Проверяет что все разделы существуют, создаёт отсутствующие.
    Возвращает {название: page_id}
    """
    global _sections
    if _sections:
        return _sections

    # Получаем существующие
    existing = get_child_pages()
    existing_names = {p["title"]: p["id"] for p in existing}

    for name, icon in SECTION_STRUCTURE.items():
        if name in existing_names:
            _sections[name] = existing_names[name]
        else:
            page = create_section(name, icon)
            _sections[name] = page["id"]

    logger.info(f"Разделы Notion готовы: {list(_sections.keys())}")
    return _sections


def add_to_section(section_name: str, title: str, content: str, icon: str = None) -> dict:
    """Добавляет страницу в указанный раздел"""
    sections = ensure_sections()
    parent_id = sections.get(section_name, NOTION_ROOT_PAGE_ID)
    return create_page(title, content, parent_page_id=parent_id, icon=icon)
