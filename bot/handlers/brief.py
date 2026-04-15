import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.ai import client
from bot.services import notion
from bot.config import CLAUDE_MODEL, NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("brief"))
async def cmd_brief(message: Message):
    """
    Генерация ТЗ из свободного описания.
    /brief Описание задачи в свободной форме
    """
    raw = message.text.replace("/brief", "", 1).strip()

    if not raw:
        await message.answer(
            "Формат: /brief Описание задачи\n\n"
            "Пример:\n"
            "/brief Нужен лендинг для курса по маркетингу, целевая — малый бизнес, "
            "нужна форма заявки и интеграция с CRM"
        )
        return

    await message.answer("Составляю ТЗ...")

    prompt = f"""Составь структурированное техническое задание для исполнителя.

Описание от заказчика: {raw}

Формат ТЗ:

# Техническое задание

## 1. Цель проекта
(что нужно получить в итоге)

## 2. Целевая аудитория
(для кого делается)

## 3. Функциональные требования
- Требование 1
- Требование 2
...

## 4. Нефункциональные требования
(скорость, дизайн, адаптив, и т.д.)

## 5. Структура / Состав работ
(конкретный список того что нужно сделать)

## 6. Контент
(какой контент нужен, кто предоставляет)

## 7. Этапы и сроки
1. Этап — срок
2. Этап — срок

## 8. Критерии приёмки
(как проверяем что работа сделана)

## 9. Не входит в scope
(что НЕ включено)

Пиши конкретно, профессионально, без воды. ТЗ должно быть готово к отправке исполнителю."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text

        notion_link = ""
        if NOTION_API_KEY:
            title = f"ТЗ: {raw[:50]}"
            page = notion.add_to_section("База знаний", title, result, icon="📋")
            notion_link = f"\n\nNotion: {page['url']}"

        if len(result) > 3500:
            await message.answer(result[:3500] + "...", parse_mode=None)
            await message.answer(f"Полное ТЗ в Notion.{notion_link}")
        else:
            await message.answer(result + notion_link, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка: {e}")
