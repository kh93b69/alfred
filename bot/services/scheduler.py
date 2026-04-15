import logging
from datetime import timezone, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Часовой пояс владельца — Караганда UTC+5
OWNER_TZ = timezone(timedelta(hours=5))

from bot.services.agent import propose_daily_tasks, daily_report, pending_tasks

logger = logging.getLogger(__name__)

# Планировщик задач
scheduler = AsyncIOScheduler()

# ID чата владельца (устанавливается при /start или /plan)
owner_chat_id: int = None

# Ссылка на бота
bot_instance = None


def set_owner(chat_id: int):
    global owner_chat_id
    owner_chat_id = chat_id
    logger.info(f"Владелец установлен: {chat_id}")


def set_bot(bot):
    global bot_instance
    bot_instance = bot


async def morning_routine():
    """Утренняя рутина: предлагает задачи с кнопками"""
    if not owner_chat_id or not bot_instance:
        logger.warning("Владелец или бот не установлены")
        return

    try:
        logger.info("Утренняя рутина...")
        tasks = await propose_daily_tasks()

        if not tasks:
            await bot_instance.send_message(
                owner_chat_id,
                "🌅 Доброе утро! База знаний пуста — загрузи документы чтобы я мог планировать."
            )
            return

        await bot_instance.send_message(
            owner_chat_id,
            f"🌅 **Доброе утро! Предлагаю {len(tasks)} задач на сегодня:**",
            parse_mode="Markdown",
        )

        all_keys = []
        for i, task in enumerate(tasks):
            output_emoji = {"document": "📄", "table": "📊", "text": "📝"}.get(task.get("output_type", "text"), "📝")
            output_label = {"document": "документ", "table": "таблица", "text": "текст"}.get(task.get("output_type", "text"), "текст")

            text = (
                f"**{i+1}. {task['name']}**\n"
                f"{task.get('description', '')}\n"
                f"{output_emoji} Результат: {output_label}"
            )

            task_key = f"task_{owner_chat_id}_{i}_{hash(task['name']) % 10000}"
            pending_tasks[task_key] = task
            all_keys.append(task_key)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{task_key}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{task_key}"),
                ]
            ])
            await bot_instance.send_message(owner_chat_id, text, parse_mode="Markdown", reply_markup=keyboard)

        # Кнопка "Подтвердить все"
        pending_tasks[f"all_{owner_chat_id}"] = all_keys
        keyboard_all = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить все", callback_data=f"approve_all:{owner_chat_id}")]
        ])
        await bot_instance.send_message(owner_chat_id, "Или подтверди все разом:", reply_markup=keyboard_all)

    except Exception as e:
        logger.error(f"Ошибка утренней рутины: {e}")
        await bot_instance.send_message(owner_chat_id, f"Ошибка утренней рутины: {e}")


async def evening_report():
    """Вечерний отчёт"""
    if not owner_chat_id or not bot_instance:
        return
    try:
        report = await daily_report()
        await bot_instance.send_message(owner_chat_id, report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка вечернего отчёта: {e}")


def start_scheduler():
    """Запускает планировщик"""
    scheduler.add_job(morning_routine, CronTrigger(hour=8, minute=0, timezone=OWNER_TZ), id="morning_routine", replace_existing=True)
    scheduler.add_job(evening_report, CronTrigger(hour=21, minute=0, timezone=OWNER_TZ), id="evening_report", replace_existing=True)
    scheduler.start()
    logger.info("Планировщик запущен: утро 8:00, вечер 21:00 (UTC+5)")
