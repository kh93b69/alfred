from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.services.scheduler import set_owner, scheduler
from bot.services import reminders

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    set_owner(message.chat.id)

    # Инициализируем напоминания с ID владельца
    reminders.init(scheduler, message.bot, message.chat.id)

    await message.answer(
        "Привет! Я Альфред — твой персональный ассистент и второй мозг.\n\n"
        "**Основное:**\n"
        "Просто напиши или надиктуй — я отвечу\n\n"
        "**Задачи и планирование:**\n"
        "/plan — спланировать задачи на день\n"
        "/execute — выполнить входящие задачи\n"
        "/task — создать задачу в Trello\n"
        "/tasks — все задачи\n"
        "/done — отметить выполненной\n"
        "/report — отчёт\n\n"
        "**База знаний:**\n"
        "/knowledge — просмотр базы\n"
        "/add — добавить заметку\n"
        "Или скинь файл (PDF, DOCX, XLSX, XMind)\n\n"
        "**Напоминания:**\n"
        "/remind 09:00 Выпить витамины\n"
        "/remind — список напоминаний\n"
        "/forget 1 — удалить\n\n"
        "**Документы:**\n"
        "/invoice — счёт на оплату\n"
        "/doc — документ из шаблона\n\n"
        "⏰ Автоматически: план в 8:00, отчёт в 21:00",
        parse_mode="Markdown",
    )
