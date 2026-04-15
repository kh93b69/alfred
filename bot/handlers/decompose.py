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


@router.message(Command("decompose"))
async def cmd_decompose(message: Message):
    """
    Декомпозиция цели на кварталы → месяцы → недели → дни.
    /decompose Цель на год
    """
    raw = message.text.replace("/decompose", "", 1).strip()

    if not raw:
        await message.answer(
            "Формат: /decompose Твоя цель\n\n"
            "Пример:\n"
            "/decompose Выйти на 1М выручки к концу года\n"
            "/decompose Запустить SaaS продукт"
        )
        return

    await message.answer(f"Декомпозирую цель: **{raw}**...", parse_mode="Markdown")

    knowledge = load_knowledge()

    prompt = f"""Ты — Альфред, стратегический ассистент. Декомпозируй цель владельца.

БАЗА ЗНАНИЙ ВЛАДЕЛЬЦА:
{knowledge if knowledge else "Нет данных"}

ЦЕЛЬ: {raw}

Разбей цель на конкретные шаги:

# Цель: {raw}

## Q2 2026 (апрель-июнь)
### Апрель
- Неделя 1: ...
- Неделя 2: ...
- Неделя 3: ...
- Неделя 4: ...
### Май
(аналогично)
### Июнь
(аналогично)

## Q3 2026 (июль-сентябрь)
(аналогично по месяцам и неделям)

## Q4 2026 (октябрь-декабрь)
(аналогично)

## Ключевые метрики
- Как измерить прогресс
- Контрольные точки

Каждый шаг должен быть конкретным и выполнимым. Учитывай базу знаний владельца."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text

        # Сохраняем в Notion если подключён
        notion_link = ""
        if NOTION_API_KEY:
            page = notion.add_to_section("Цели", f"Декомпозиция: {raw[:50]}", result, icon="🎯")
            notion_link = f"\n\nNotion: {page['url']}"

        # Отправляем в Telegram (обрезаем если длинное)
        if len(result) > 3500:
            await message.answer(result[:3500] + "...", parse_mode=None)
            await message.answer(f"Полная версия в Notion.{notion_link}")
        else:
            await message.answer(result + notion_link, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка декомпозиции: {e}")
        await message.answer(f"Ошибка: {e}")
