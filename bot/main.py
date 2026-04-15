import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers import (
    start, knowledge, tasks, docs, invoice, files, voice, chat, remind,
    notion_cmd, decompose, priority, summary, contacts, idea, brief, energy,
)
from bot.handlers import agent as agent_handler
from bot.services.scheduler import start_scheduler, set_bot, scheduler
from bot.services import reminders

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота"""

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не задан! Добавь его в .env файл.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем обработчики (порядок важен — команды первыми, chat последним)
    dp.include_router(start.router)
    dp.include_router(knowledge.router)
    dp.include_router(agent_handler.router)
    dp.include_router(tasks.router)
    dp.include_router(remind.router)
    dp.include_router(notion_cmd.router)
    dp.include_router(decompose.router)
    dp.include_router(priority.router)
    dp.include_router(summary.router)
    dp.include_router(contacts.router)
    dp.include_router(idea.router)
    dp.include_router(brief.router)
    dp.include_router(energy.router)
    dp.include_router(docs.router)
    dp.include_router(invoice.router)
    dp.include_router(files.router)
    dp.include_router(voice.router)
    dp.include_router(chat.router)  # последним — ловит все остальные сообщения

    # Запускаем планировщик
    set_bot(bot)
    start_scheduler()

    # Инициализируем напоминания (загрузятся при первом /start когда узнаем owner_chat_id)
    reminders.init(scheduler, bot, None)

    logger.info("Альфред запущен! Планировщик активен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
