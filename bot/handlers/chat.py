import json
import os
import logging
from aiogram import Router
from aiogram.types import Message, FSInputFile

from bot.services.ai import ask_alfred, client
from bot.services import trello, notion
from bot.services.invoice import generate_invoice
from bot.services.knowledge import add_note
from bot.services import reminders as reminders_service
from bot.config import (
    CLAUDE_MODEL, NOTION_API_KEY,
    TRELLO_LIST_INBOX, TRELLO_LIST_DOING, TRELLO_LIST_DONE,
)

router = Router()
logger = logging.getLogger(__name__)

# Описание инструментов для Claude
TOOLS_DESCRIPTION = """У тебя есть доступ к следующим инструментам. Если пользователь просит что-то сделать — используй нужный инструмент.

ИНСТРУМЕНТЫ:
1. CREATE_TASK — создать задачу в Trello
2. CREATE_INVOICE — сгенерировать счёт на оплату
3. CREATE_REMINDER — создать напоминание на определённое время
4. SAVE_TO_NOTION — сохранить информацию в Notion (регламент, заметка, идея)
5. SAVE_CONTACT — сохранить контакт
6. GENERATE_IDEAS — сгенерировать идеи по теме
7. CREATE_BRIEF — составить ТЗ
8. MARK_DONE — отметить задачу выполненной
9. ADD_TICKTICK — добавить задачу в TickTick
10. NONE — просто ответить текстом, без инструментов

Когда пользователь просит выполнить действие, ответь JSON в формате:
{"tool": "НАЗВАНИЕ_ИНСТРУМЕНТА", "params": {параметры}}

Параметры для каждого инструмента:
- CREATE_TASK: {"name": "название", "description": "описание"}
- CREATE_INVOICE: {"НОМЕР_СЧЁТА": "...", "ДАТА_СЧЁТА": "...", "ПОКУПАТЕЛЬ_БИН": "...", "ПОКУПАТЕЛЬ_НАЗВАНИЕ": "...", "ПОКУПАТЕЛЬ_АДРЕС": "...", "НОМЕР_ДОГОВОРА": "...", "НАЗВАНИЕ_ДОГОВОРА": "...", "НАИМЕНОВАНИЕ_УСЛУГИ": "...", "СУММА": "..."}
- CREATE_REMINDER: {"time": "HH:MM", "text": "текст напоминания", "days": "daily или mon,tue,..."}
- SAVE_TO_NOTION: {"section": "Регламенты/База знаний/Саммари/Идеи/Цели", "title": "название", "content": "текст"}
- SAVE_CONTACT: {"name": "имя", "description": "описание"}
- GENERATE_IDEAS: {"topic": "тема"}
- CREATE_BRIEF: {"description": "описание задачи"}
- MARK_DONE: {"task_name": "часть названия задачи"}
- ADD_TICKTICK: {"title": "название задачи"}
- NONE: {"reply": "текстовый ответ пользователю"}

Если пользователь говорит "добавь в тиктик" или "запиши задачу в тиктик" — используй ADD_TICKTICK.
Если просто "создай задачу" без уточнения — используй CREATE_TASK (Trello).

ВАЖНО: Если из сообщения не хватает данных для инструмента — уточни. Верни ТОЛЬКО JSON, без текста вокруг."""


async def _detect_and_execute(message: Message, user_text: str):
    """Определяет намерение и выполняет действие"""

    # Спрашиваем Claude что делать
    detect_prompt = f"{TOOLS_DESCRIPTION}\n\nСообщение пользователя:\n{user_text}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": detect_prompt}],
    )

    raw_response = response.content[0].text.strip()

    # Пытаемся распарсить JSON
    try:
        # Убираем markdown если есть
        json_text = raw_response
        if "```" in json_text:
            json_text = json_text.split("```")[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
            json_text = json_text.strip()

        # Ищем JSON в ответе
        start = json_text.find("{")
        end = json_text.rfind("}") + 1
        if start >= 0 and end > start:
            json_text = json_text[start:end]

        action = json.loads(json_text)
        tool = action.get("tool", "NONE")
        params = action.get("params", {})

    except (json.JSONDecodeError, KeyError):
        # Не смог распарсить — просто отвечаем через обычный чат
        response = await ask_alfred(message.chat.id, user_text)
        await message.answer(response)
        return

    # Выполняем инструмент
    if tool == "NONE":
        # Всегда через ask_alfred — он загружает базу знаний
        response = await ask_alfred(message.chat.id, user_text)
        await message.answer(response)

    elif tool == "CREATE_TASK":
        name = params.get("name", "")
        desc = params.get("description", "")
        if not name:
            await message.answer("Уточни название задачи.")
            return
        card = trello.create_card(name=name, description=desc)
        await message.answer(
            f"📋 Задача создана в Trello: **{name}**\nВыполняю...",
            parse_mode="Markdown",
        )

        # Сразу выполняем задачу
        try:
            from bot.services.agent import execute_task
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            result = await execute_task(card["id"], name, desc, "text")

            preview = result["text"][:3500] + "..." if len(result["text"]) > 3500 else result["text"]
            await message.answer(f"✅ **{name}** — выполнено:\n\n{preview}", parse_mode="Markdown")

            # Отправляем файл если есть
            if result.get("file_path") and os.path.exists(result["file_path"]):
                doc_file = FSInputFile(result["file_path"])
                await message.answer_document(doc_file, caption=f"📎 {result['file_name']}")
                os.remove(result["file_path"])
        except Exception as e:
            logger.error(f"Ошибка выполнения задачи: {e}")
            await message.answer(f"Задача создана, но при выполнении ошибка: {e}")

    elif tool == "CREATE_INVOICE":
        await message.answer("Генерирую счёт...")
        try:
            output_path = generate_invoice(params)
            doc_file = FSInputFile(output_path)
            номер = params.get("НОМЕР_СЧЁТА", "")
            покупатель = params.get("ПОКУПАТЕЛЬ_НАЗВАНИЕ", "")
            await message.answer_document(
                doc_file,
                caption=f"Счёт №{номер} для {покупатель}",
            )
            os.remove(output_path)
        except Exception as e:
            await message.answer(f"Ошибка генерации счёта: {e}")

    elif tool == "CREATE_REMINDER":
        time_str = params.get("time", "")
        text = params.get("text", "")
        days = params.get("days", "daily")
        if not time_str or not text:
            await message.answer("Уточни время и текст напоминания.")
            return
        r = reminders_service.add_reminder(text=text, time=time_str, days=days)
        days_label = "ежедневно" if days == "daily" else days
        await message.answer(
            f"✅ Напоминание создано:\n🔔 **{time_str}** ({days_label})\n{text}",
            parse_mode="Markdown",
        )

    elif tool == "SAVE_TO_NOTION":
        if not NOTION_API_KEY:
            await message.answer("Notion не настроен.")
            return
        section = params.get("section", "База знаний")
        title = params.get("title", "Без названия")
        content = params.get("content", "")
        await message.answer(f"Сохраняю в Notion → {section}...")
        page = notion.add_to_section(section, title, content)
        await message.answer(
            f"✅ Сохранено: **{title}**\nNotion: {page['url']}",
            parse_mode="Markdown",
        )

    elif tool == "SAVE_CONTACT":
        if not NOTION_API_KEY:
            await message.answer("Notion не настроен.")
            return
        name = params.get("name", "")
        desc = params.get("description", "")
        import datetime
        content = f"# {name}\n\n{desc}\n\nДобавлен: {datetime.datetime.now().strftime('%d.%m.%Y')}"
        page = notion.add_to_section("Контакты", name, content, icon="👤")
        await message.answer(
            f"👤 Контакт сохранён: **{name}**\nNotion: {page['url']}",
            parse_mode="Markdown",
        )

    elif tool == "GENERATE_IDEAS":
        topic = params.get("topic", "")
        await message.answer(f"Генерирую идеи: **{topic}**...", parse_mode="Markdown")
        from bot.services.knowledge import load_knowledge
        knowledge = load_knowledge()
        prompt = f"Сгенерируй 10 конкретных бизнес-идей по теме: {topic}\n\nБаза знаний:\n{knowledge if knowledge else 'Нет'}\n\nКаждая идея: название, суть (2 предложения), первый шаг."
        resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=4096, messages=[{"role": "user", "content": prompt}])
        result = resp.content[0].text
        if NOTION_API_KEY:
            page = notion.add_to_section("Идеи", f"Идеи: {topic[:50]}", result, icon="💡")
            result += f"\n\nNotion: {page['url']}"
        await message.answer(result[:4000], parse_mode=None)

    elif tool == "CREATE_BRIEF":
        desc = params.get("description", "")
        await message.answer("Составляю ТЗ...")
        prompt = f"Составь структурированное техническое задание:\n{desc}\n\nФормат: Цель, Требования, Этапы, Критерии приёмки."
        resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=4096, messages=[{"role": "user", "content": prompt}])
        result = resp.content[0].text
        if NOTION_API_KEY:
            page = notion.add_to_section("База знаний", f"ТЗ: {desc[:50]}", result, icon="📋")
            result += f"\n\nNotion: {page['url']}"
        await message.answer(result[:4000], parse_mode=None)

    elif tool == "MARK_DONE":
        task_name = params.get("task_name", "").lower()
        cards = trello.get_cards()
        found = None
        for card in cards:
            if task_name in card["name"].lower() and card["idList"] != TRELLO_LIST_DONE:
                found = card
                break
        if found:
            trello.move_to_done(found["id"])
            await message.answer(f"✅ Задача выполнена: **{found['name']}**", parse_mode="Markdown")
        else:
            await message.answer(f"Задача с '{task_name}' не найдена.")

    elif tool == "ADD_TICKTICK":
        from bot.services import ticktick
        title = params.get("title", "")
        if not title:
            await message.answer("Уточни название задачи для TickTick.")
            return
        if not ticktick.is_connected():
            await message.answer("TickTick не подключён. Используй /ticktick")
            return
        try:
            ticktick.create_task(title=title)
            await message.answer(f"✅ Задача в TickTick: **{title}**", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Ошибка TickTick: {e}")

    else:
        # Неизвестный инструмент — обычный ответ
        response = await ask_alfred(message.chat.id, user_text)
        await message.answer(response)


@router.message()
async def handle_text(message: Message):
    """Обработчик всех текстовых сообщений — умный роутинг"""

    if not message.text:
        return

    logger.info(f"Сообщение от {message.from_user.full_name}: {message.text[:50]}...")
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        await _detect_and_execute(message, message.text)
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
        # Фолбэк на обычный чат
        try:
            response = await ask_alfred(message.chat.id, message.text)
            await message.answer(response)
        except Exception as e2:
            logger.error(f"Фолбэк тоже упал: {e2}")
            await message.answer("Произошла ошибка. Попробуй ещё раз.")
