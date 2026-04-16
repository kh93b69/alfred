import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import ticktick
from bot.config import TICKTICK_CLIENT_ID

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("ticktick"))
async def cmd_ticktick(message: Message):
    """Подключение и управление TickTick"""
    if not TICKTICK_CLIENT_ID:
        await message.answer("TickTick не настроен. Добавь TICKTICK_CLIENT_ID в переменные.")
        return

    raw = message.text.replace("/ticktick", "", 1).strip()

    # Если передан код авторизации
    if raw and len(raw) > 10 and not raw.startswith("task"):
        try:
            ticktick.exchange_code(raw)
            await message.answer("✅ TickTick подключён! Теперь можешь использовать /tt для задач.")
        except Exception as e:
            await message.answer(f"Ошибка авторизации: {e}")
        return

    # Если уже подключён — показать статус
    if ticktick.is_connected():
        try:
            projects = ticktick.get_projects()
            text = "✅ **TickTick подключён**\n\nСписки:\n"
            for p in projects:
                text += f"• {p['name']}\n"
            text += "\n**Команды:**\n"
            text += "/tt задачи — все задачи\n"
            text += "/tt добавить Текст — создать задачу\n"
            text += "Или просто скажи голосом — Альфред добавит в TickTick"
            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
        return

    # Не подключён — дать ссылку
    try:
        auth_url = ticktick.get_auth_url()
        await message.answer(
            f"**Подключение TickTick:**\n\n"
            f"1. Перейди по ссылке:\n{auth_url}\n\n"
            f"2. Нажми 'Authorize'\n"
            f"3. Тебя перекинет на localhost — это нормально\n"
            f"4. Скопируй из адресной строки параметр code=XXXXX\n"
            f"5. Отправь мне: /ticktick XXXXX",
        )
    except Exception as e:
        logger.error(f"Ошибка TickTick auth: {e}")
        await message.answer(f"Ошибка: {e}")


@router.message(Command("tt"))
async def cmd_tt(message: Message):
    """Быстрые команды TickTick"""
    if not ticktick.is_connected():
        await message.answer("TickTick не подключён. Используй /ticktick")
        return

    raw = message.text.replace("/tt", "", 1).strip()

    if not raw or raw == "задачи" or raw == "tasks":
        # Показать задачи
        try:
            all_tasks = ticktick.get_all_tasks()
            if not all_tasks:
                await message.answer("Задач нет.")
                return

            # Группируем по проектам
            by_project: dict[str, list] = {}
            for t in all_tasks:
                proj = t.get("_project_name", "Без списка")
                if proj not in by_project:
                    by_project[proj] = []
                by_project[proj].append(t)

            text = "📋 **Задачи TickTick:**\n\n"
            for proj_name, tasks in by_project.items():
                text += f"**{proj_name}:**\n"
                for t in tasks[:10]:
                    status = "✅" if t.get("status", 0) == 2 else "⬜"
                    text += f"  {status} {t['title']}\n"
                if len(tasks) > 10:
                    text += f"  ...и ещё {len(tasks) - 10}\n"
                text += "\n"

            await message.answer(text[:4000], parse_mode="Markdown")

        except Exception as e:
            await message.answer(f"Ошибка: {e}")
        return

    if raw.startswith("добавить ") or raw.startswith("add "):
        # Создать задачу
        task_text = raw.replace("добавить ", "").replace("add ", "").strip()
        if not task_text:
            await message.answer("Укажи текст задачи.")
            return

        try:
            task = ticktick.create_task(title=task_text)
            await message.answer(f"✅ Задача добавлена в TickTick: **{task_text}**", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
        return

    # Если просто текст — создаём задачу
    try:
        task = ticktick.create_task(title=raw)
        await message.answer(f"✅ Задача добавлена: **{raw}**", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
