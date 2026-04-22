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
    reminders.init(scheduler, message.bot, message.chat.id)

    await message.answer(
        "Привет! Я **Альфред** — твой второй мозг и персональный ассистент.\n\n"

        "🧠 **Общение:**\n"
        "Просто напиши или надиктуй — я отвечу\n\n"

        "📋 **Задачи и планирование:**\n"
        "/plan — спланировать день (с кнопками)\n"
        "/execute — выполнить входящие задачи\n"
        "/task — создать задачу в Trello\n"
        "/tasks — все задачи на доске\n"
        "/done — отметить выполненной\n"
        "/priority — приоритизация (Эйзенхауэр)\n"
        "/report — отчёт по задачам\n\n"

        "🎯 **Цели и стратегия:**\n"
        "/decompose — декомпозиция цели\n"
        "/idea — генератор идей\n\n"

        "📓 **Notion:**\n"
        "/notion — разделы и заметки\n"
        "/reg — написать регламент\n"
        "/summary — саммари книг/видео\n"
        "/contact — сохранить контакт\n"
        "/brief — составить ТЗ\n\n"

        "📂 **Документы:**\n"
        "/invoice — счёт на оплату\n"
        "/doc — документ из шаблона\n"
        "Или скинь файл (PDF, DOCX, XLSX, XMind)\n\n"

        "⚡ **Привычки и энергия:**\n"
        "/habit — отметить привычки\n"
        "/habit add 09:00 Витамины — добавить\n"
        "/habit stats — статистика привычек\n"
        "/energy — отметить энергию\n"
        "/energy stats — статистика энергии\n"
        "/remind 09:00 Текст — напоминание\n"
        "/remind — список напоминаний\n"
        "/forget 1 — удалить напоминание\n\n"

        "📈 **Обзоры и аналитика:**\n"
        "/weekly — обзор недели (автоматически в вс 20:00)\n"
        "/tt анализ — анализ задач TickTick\n\n"

        "⏰ **Автоматически:**\n"
        "08:00 — брифинг + план дня\n"
        "21:00 — отчёт + энергия",
        parse_mode="Markdown",
    )
