import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import notion
from bot.config import NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("contact"))
async def cmd_contact(message: Message):
    """
    Сохранить контакт в базу.
    /contact Имя | Кто, откуда, о чём договорились
    """
    if not NOTION_API_KEY:
        await message.answer("Notion не настроен.")
        return

    raw = message.text.replace("/contact", "", 1).strip()

    if not raw or "|" not in raw:
        await message.answer(
            "Формат: /contact Имя | Описание\n\n"
            "Примеры:\n"
            "/contact Марат Иванов | CEO TechCorp, познакомились на конференции, "
            "договорились созвониться по партнёрству\n\n"
            "/contact Айгуль | Дизайнер, делает логотипы, 50к за проект, @aigul_design"
        )
        return

    name, description = raw.split("|", 1)
    name = name.strip()
    description = description.strip()

    content = f"""# {name}

## Контактная информация
{description}

## Дата добавления
{__import__('datetime').datetime.now().strftime('%d.%m.%Y')}

## История взаимодействия
- Добавлен в базу

## Заметки
(добавляй заметки после встреч и звонков)
"""

    try:
        page = notion.add_to_section("Контакты", name, content, icon="👤")
        await message.answer(
            f"👤 Контакт сохранён: **{name}**\n"
            f"Notion: {page['url']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка: {e}")
