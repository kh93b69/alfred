from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.knowledge import list_files, add_note

router = Router()


@router.message(Command("knowledge"))
async def cmd_knowledge(message: Message):
    """Показать содержимое базы знаний"""
    files = list_files()

    if not files:
        await message.answer(
            "База знаний пуста.\n\n"
            "Чтобы добавить заметку, используй:\n"
            "/add Название | Текст заметки\n\n"
            "Или отправь мне файл (.txt, .pdf, .docx) — я его сохраню."
        )
        return

    text = "📂 **База знаний Альфреда:**\n\n"
    for f in files:
        name = f.rsplit(".", 1)[0]
        text += f"• {name}\n"

    text += f"\nВсего файлов: {len(files)}"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("add"))
async def cmd_add(message: Message):
    """Добавить заметку в базу знаний: /add Название | Текст"""
    # Убираем /add из начала
    raw = message.text.replace("/add", "", 1).strip()

    if not raw or "|" not in raw:
        await message.answer(
            "Формат: /add Название | Текст заметки\n\n"
            "Пример:\n"
            "/add Цели на 2026 | 1. Запустить SaaS продукт 2. Выйти на 1М выручки"
        )
        return

    title, content = raw.split("|", 1)
    title = title.strip()
    content = content.strip()

    if not title or not content:
        await message.answer("Нужно указать и название, и текст.")
        return

    filename = add_note(title, content)
    await message.answer(f"Сохранено в базу знаний: **{title}**", parse_mode="Markdown")
