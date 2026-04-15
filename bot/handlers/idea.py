import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.ai import client
from bot.services.knowledge import load_knowledge
from bot.services import notion
from bot.config import CLAUDE_MODEL, NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("idea"))
async def cmd_idea(message: Message):
    """
    Генератор идей.
    /idea тема — 10 идей по теме
    """
    raw = message.text.replace("/idea", "", 1).strip()

    if not raw:
        await message.answer(
            "Формат: /idea тема\n\n"
            "Примеры:\n"
            "/idea контент для Instagram\n"
            "/idea как увеличить средний чек\n"
            "/idea новый продукт для B2B"
        )
        return

    await message.answer(f"Генерирую идеи по теме: **{raw}**...", parse_mode="Markdown")

    knowledge = load_knowledge()

    prompt = f"""Ты — Альфред, креативный бизнес-ассистент.

БАЗА ЗНАНИЙ ВЛАДЕЛЬЦА:
{knowledge if knowledge else "Нет данных"}

Сгенерируй 10 конкретных идей по теме: {raw}

Формат для каждой идеи:
## Идея N: Название
**Суть:** что конкретно делать (2-3 предложения)
**Почему сработает:** обоснование
**Первый шаг:** что сделать прямо сейчас

Идеи должны быть:
- Конкретными и реализуемыми
- Учитывать бизнес владельца (если есть в базе знаний)
- Разнообразными (от простых до амбициозных)
- С учётом рынка Казахстана/СНГ"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text

        # Сохраняем в Notion
        notion_link = ""
        if NOTION_API_KEY:
            page = notion.add_to_section("Идеи", f"Идеи: {raw[:50]}", result, icon="💡")
            notion_link = f"\n\nNotion: {page['url']}"

        if len(result) > 3500:
            await message.answer(result[:3500] + "...", parse_mode=None)
            await message.answer(f"Все 10 идей в Notion.{notion_link}")
        else:
            await message.answer(result + notion_link, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка: {e}")
