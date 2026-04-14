import json
import os
import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from bot.services.agent import propose_daily_tasks, execute_task, daily_report, pending_tasks
from bot.services import trello
from bot.services.scheduler import set_owner

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("plan"))
async def cmd_plan(message: Message):
    """Спланировать день — предлагает задачи с кнопками подтверждения"""
    set_owner(message.chat.id)
    await message.answer("Анализирую твою базу знаний и текущие задачи...")

    try:
        tasks = await propose_daily_tasks()

        if not tasks:
            await message.answer(
                "База знаний пуста — не из чего планировать.\n"
                "Загрузи документы, скинь файлы или используй /add."
            )
            return

        await message.answer(f"Предлагаю **{len(tasks)} задач** на сегодня:", parse_mode="Markdown")

        all_keys = []
        for i, task in enumerate(tasks):
            output_emoji = {"document": "📄", "table": "📊", "text": "📝"}.get(task.get("output_type", "text"), "📝")
            output_label = {"document": "документ", "table": "таблица", "text": "текст"}.get(task.get("output_type", "text"), "текст")

            text = (
                f"**{i+1}. {task['name']}**\n"
                f"{task.get('description', '')}\n"
                f"{output_emoji} Результат: {output_label}"
            )

            task_key = f"task_{message.chat.id}_{i}_{hash(task['name']) % 10000}"
            pending_tasks[task_key] = task
            all_keys.append(task_key)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{task_key}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{task_key}"),
                ]
            ])
            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

        # Кнопка "Подтвердить все"
        pending_tasks[f"all_{message.chat.id}"] = all_keys
        keyboard_all = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить все", callback_data=f"approve_all:{message.chat.id}")]
        ])
        await message.answer("Или подтверди все разом:", reply_markup=keyboard_all)

    except Exception as e:
        logger.error(f"Ошибка планирования: {e}")
        await message.answer(f"Ошибка: {e}")


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
    """Подтверждение одной задачи"""
    task_key = callback.data.replace("approve:", "")
    task = pending_tasks.get(task_key)

    if not task:
        await callback.answer("Задача уже обработана")
        return

    # Мгновенно отвечаем на callback (до истечения 30 сек)
    await callback.answer("Принято! Выполняю...")

    # Убираем кнопки сразу
    try:
        await callback.message.edit_text(
            f"⏳ **{task['name']}**\n"
            f"{task.get('description', '')}\n\n"
            f"Создаю в Trello и выполняю задачу...",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    # Удаляем из ожидающих сразу, чтобы повторное нажатие не сработало
    del pending_tasks[task_key]

    try:
        # Создаём карточку в Trello
        card = trello.create_card(
            name=task["name"],
            description=task.get("description", ""),
        )

        # Выполняем задачу (может занять 30-90 секунд)
        output_type = task.get("output_type", "text")
        result = await execute_task(card["id"], task["name"], task.get("description", ""), output_type)

        # Обновляем сообщение
        preview = result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"]
        try:
            await callback.message.edit_text(
                f"✅ **{task['name']}** — выполнено!\n\n"
                f"{preview}\n\n"
                f"Результат в карточке Trello.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        # Отправляем файл если есть
        if result["file_path"] and os.path.exists(result["file_path"]):
            doc_file = FSInputFile(result["file_path"])
            await callback.message.answer_document(doc_file, caption=f"📎 {result['file_name']}")
            os.remove(result["file_path"])

    except Exception as e:
        logger.error(f"Ошибка выполнения задачи: {e}")
        try:
            await callback.message.edit_text(
                f"❌ **{task['name']}** — ошибка: {e}",
                parse_mode="Markdown",
            )
        except Exception:
            await callback.message.answer(f"Ошибка выполнения '{task['name']}': {e}")


@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery):
    """Отклонение задачи"""
    task_key = callback.data.replace("reject:", "")
    task = pending_tasks.get(task_key)

    if not task:
        await callback.answer("Задача уже обработана")
        return

    # Мгновенно отвечаем
    await callback.answer("Отклонено")

    del pending_tasks[task_key]

    try:
        await callback.message.edit_text(
            f"❌ ~~{task['name']}~~ — отклонена",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("approve_all:"))
async def on_approve_all(callback: CallbackQuery):
    """Подтверждение всех задач"""
    chat_id = callback.data.replace("approve_all:", "")
    all_keys_key = f"all_{chat_id}"
    task_keys = pending_tasks.get(all_keys_key, [])

    if not task_keys:
        await callback.answer("Задачи уже обработаны")
        return

    # Мгновенно отвечаем
    await callback.answer("Все задачи приняты!")

    # Собираем задачи и удаляем из ожидающих
    tasks_to_do = []
    for tk in task_keys:
        task = pending_tasks.get(tk)
        if task:
            tasks_to_do.append(task)
            del pending_tasks[tk]
    del pending_tasks[all_keys_key]

    await callback.message.edit_text(
        f"✅ **Все {len(tasks_to_do)} задач подтверждены.** Начинаю выполнение...",
        parse_mode="Markdown",
    )

    for i, task in enumerate(tasks_to_do):
        try:
            await callback.message.answer(
                f"⏳ [{i+1}/{len(tasks_to_do)}] Выполняю: **{task['name']}**...",
                parse_mode="Markdown",
            )

            card = trello.create_card(
                name=task["name"],
                description=task.get("description", ""),
            )

            output_type = task.get("output_type", "text")
            result = await execute_task(card["id"], task["name"], task.get("description", ""), output_type)

            # Отправляем результат
            if result["file_path"] and os.path.exists(result["file_path"]):
                doc_file = FSInputFile(result["file_path"])
                await callback.message.answer_document(
                    doc_file,
                    caption=f"✅ **{task['name']}**",
                    parse_mode="Markdown",
                )
                os.remove(result["file_path"])
            else:
                preview = result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"]
                await callback.message.answer(
                    f"✅ **{task['name']}**\n\n{preview}",
                    parse_mode="Markdown",
                )

        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await callback.message.answer(f"❌ Ошибка при '{task['name']}': {e}")

    await callback.message.answer(
        f"🎯 **Готово! Выполнено {len(tasks_to_do)} задач.**\n"
        f"Результаты в Trello → колонка 'На проверку'.",
        parse_mode="Markdown",
    )


@router.message(Command("execute"))
async def cmd_execute(message: Message):
    """Выполнить все задачи из 'Входящие'"""
    set_owner(message.chat.id)

    from bot.config import TRELLO_LIST_INBOX
    cards = trello.get_cards(TRELLO_LIST_INBOX)

    if not cards:
        await message.answer("В колонке 'Входящие' нет задач.")
        return

    await message.answer(f"Выполняю {len(cards)} задач из 'Входящие'...")

    for i, card in enumerate(cards):
        await message.answer(f"⏳ [{i+1}/{len(cards)}] **{card['name']}**...", parse_mode="Markdown")

        result = await execute_task(card["id"], card["name"], card.get("desc", ""), "text")

        if result["file_path"] and os.path.exists(result["file_path"]):
            doc_file = FSInputFile(result["file_path"])
            await message.answer_document(doc_file, caption=f"✅ {card['name']}")
            os.remove(result["file_path"])
        else:
            preview = result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"]
            await message.answer(f"✅ **{card['name']}**\n\n{preview}", parse_mode="Markdown")

    await message.answer("🎯 Все задачи выполнены. Проверь в Trello → 'На проверку'.")


@router.message(Command("report"))
async def cmd_report(message: Message):
    """Отчёт по задачам"""
    try:
        report = await daily_report()
        await message.answer(report, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
