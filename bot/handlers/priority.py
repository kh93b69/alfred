import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.ai import client
from bot.services import trello
from bot.config import CLAUDE_MODEL, TRELLO_LIST_INBOX, TRELLO_LIST_DOING, TRELLO_LIST_REVIEW

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("priority"))
async def cmd_priority(message: Message):
    """
    Приоритизация задач по матрице Эйзенхауэра.
    Анализирует все задачи на доске и расставляет приоритеты.
    """
    await message.answer("Анализирую задачи по матрице Эйзенхауэра...")

    try:
        # Собираем все задачи
        all_cards = trello.get_cards()
        if not all_cards:
            await message.answer("На доске нет задач.")
            return

        tasks_text = ""
        for card in all_cards:
            list_name = "Входящие"
            if card["idList"] == TRELLO_LIST_DOING:
                list_name = "В работе"
            elif card["idList"] == TRELLO_LIST_REVIEW:
                list_name = "На проверку"
            tasks_text += f"- [{list_name}] {card['name']}: {card.get('desc', '')[:100]}\n"

        prompt = f"""Проанализируй задачи по матрице Эйзенхауэра и расставь приоритеты.

ЗАДАЧИ:
{tasks_text}

Распредели каждую задачу по квадрантам:

🔴 **СРОЧНО + ВАЖНО** (делать первым):
(задачи)

🟡 **ВАЖНО, НЕ СРОЧНО** (запланировать):
(задачи)

🟠 **СРОЧНО, НЕ ВАЖНО** (делегировать):
(задачи)

⚪ **НЕ СРОЧНО, НЕ ВАЖНО** (убрать):
(задачи)

## Рекомендация на сегодня
Конкретный план: что делать первым, вторым, третьим.

Будь конкретным. Объясни почему каждая задача попала в свой квадрант."""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text

        if len(result) > 4000:
            await message.answer(result[:4000] + "...", parse_mode=None)
        else:
            await message.answer(result, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка приоритизации: {e}")
        await message.answer(f"Ошибка: {e}")
