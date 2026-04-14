import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import trello
from bot.config import TRELLO_LIST_INBOX, TRELLO_LIST_DOING, TRELLO_LIST_REVIEW, TRELLO_LIST_DONE

router = Router()
logger = logging.getLogger(__name__)

# Маппинг названий списков для отображения
LIST_NAMES = {}


def _get_list_name(list_id: str) -> str:
    """Получает название списка по ID (с кешированием)"""
    if not LIST_NAMES:
        for lst in trello.get_lists():
            LIST_NAMES[lst["id"]] = lst["name"]
    return LIST_NAMES.get(list_id, "Неизвестно")


@router.message(Command("task"))
async def cmd_task(message: Message):
    """
    Создать задачу в Trello.
    Формат: /task Название задачи
    Или: /task Название | Описание задачи
    """
    raw = message.text.replace("/task", "", 1).strip()

    if not raw:
        await message.answer(
            "Формат: /task Название задачи\n"
            "Или: /task Название | Подробное описание\n\n"
            "Пример:\n"
            "/task Подготовить презентацию для инвестора\n"
            "/task Написать регламент | Регламент для отдела продаж по работе с CRM"
        )
        return

    # Разделяем название и описание
    if "|" in raw:
        name, desc = raw.split("|", 1)
        name = name.strip()
        desc = desc.strip()
    else:
        name = raw
        desc = ""

    try:
        card = trello.create_card(name=name, description=desc)
        url = card.get("shortUrl", "")

        await message.answer(
            f"Задача создана в Trello:\n\n"
            f"**{name}**\n"
            f"Колонка: Входящие\n"
            f"Ссылка: {url}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Ошибка создания карточки: {e}")
        await message.answer(f"Ошибка при создании задачи: {e}")


@router.message(Command("tasks"))
async def cmd_tasks(message: Message):
    """Показать все задачи на доске"""
    try:
        cards = trello.get_cards()

        if not cards:
            await message.answer("Доска пуста — задач нет.")
            return

        # Группируем карточки по спискам
        by_list: dict[str, list] = {}
        for card in cards:
            lid = card["idList"]
            if lid not in by_list:
                by_list[lid] = []
            by_list[lid].append(card["name"])

        # Порядок списков
        order = [
            (TRELLO_LIST_INBOX, "📥 Входящие"),
            (TRELLO_LIST_DOING, "🔨 В работе"),
            (TRELLO_LIST_REVIEW, "👀 На проверку"),
            (TRELLO_LIST_DONE, "✅ Готово"),
        ]

        text = "**Задачи на доске Альфреда:**\n\n"
        for list_id, list_name in order:
            items = by_list.get(list_id, [])
            if items:
                text += f"{list_name} ({len(items)}):\n"
                for item in items:
                    text += f"  • {item}\n"
                text += "\n"

        total = len(cards)
        text += f"Всего задач: {total}"
        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка получения задач: {e}")
        await message.answer(f"Ошибка при загрузке задач: {e}")


@router.message(Command("done"))
async def cmd_done(message: Message):
    """
    Пометить задачу как выполненную.
    Формат: /done Название задачи (ищет по совпадению)
    """
    raw = message.text.replace("/done", "", 1).strip().lower()

    if not raw:
        await message.answer("Формат: /done Название задачи (или часть названия)")
        return

    try:
        cards = trello.get_cards()
        # Ищем карточку по частичному совпадению
        found = None
        for card in cards:
            if raw in card["name"].lower() and card["idList"] != TRELLO_LIST_DONE:
                found = card
                break

        if not found:
            await message.answer(f"Задача с '{raw}' не найдена или уже выполнена.")
            return

        trello.move_to_done(found["id"])
        await message.answer(f"Задача выполнена: **{found['name']}** ✅", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка: {e}")
