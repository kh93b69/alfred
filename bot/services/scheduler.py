import logging
from datetime import timezone, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Часовой пояс владельца — Караганда UTC+5
OWNER_TZ = timezone(timedelta(hours=5))

from bot.services.agent import propose_daily_tasks, daily_report, pending_tasks
from bot.services.briefing import build_morning_briefing
from bot.services import habits

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

        # Сначала брифинг
        briefing = await build_morning_briefing()
        await bot_instance.send_message(owner_chat_id, briefing, parse_mode="Markdown")

        # Потом задачи
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
    """Вечерний отчёт + запрос энергии"""
    if not owner_chat_id or not bot_instance:
        return
    try:
        report = await daily_report()
        await bot_instance.send_message(owner_chat_id, report, parse_mode="Markdown")

        # Запрос энергии
        buttons = []
        row = []
        for i in range(1, 11):
            row.append(InlineKeyboardButton(text=str(i), callback_data=f"energy:{i}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await bot_instance.send_message(
            owner_chat_id,
            "⚡ **Как энергия сегодня?** (1-10)",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"Ошибка вечернего отчёта: {e}")


async def weekly_review_job():
    """Еженедельный обзор — каждое воскресенье в 20:00"""
    if not owner_chat_id or not bot_instance:
        return
    try:
        logger.info("Еженедельный обзор...")
        # Вызываем через команду /weekly
        from bot.handlers.weekly import cmd_weekly
        # Создаём фиктивное сообщение
        class FakeMessage:
            def __init__(self, chat_id, bot):
                self.chat = type("c", (), {"id": chat_id})()
                self.bot = bot
            async def answer(self, text, parse_mode=None, reply_markup=None):
                await bot_instance.send_message(owner_chat_id, text, parse_mode=parse_mode)
            async def answer_document(self, doc, caption=None):
                await bot_instance.send_document(owner_chat_id, doc, caption=caption)
            @property
            def text(self):
                return "/weekly"
        fake = FakeMessage(owner_chat_id, bot_instance)
        await cmd_weekly(fake)
    except Exception as e:
        logger.error(f"Ошибка weekly: {e}")


async def habits_check_job():
    """Утренний чек привычек — в 9:00"""
    if not owner_chat_id or not bot_instance:
        return
    try:
        all_habits = habits.get_habits()
        if not all_habits:
            return

        text = "🌱 **Утренний чек привычек:**\n\n"
        for h in all_habits:
            streak = habits.get_streak(h["id"])
            text += f"**{h['name']}** 🔥 {streak} дней\n"
        text += "\nОтметь выполненные:"

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = []
        for h in all_habits:
            row = [
                InlineKeyboardButton(text=f"✅ {h['name'][:25]}", callback_data=f"habit_yes:{h['id']}"),
                InlineKeyboardButton(text="❌", callback_data=f"habit_no:{h['id']}"),
            ]
            buttons.append(row)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await bot_instance.send_message(owner_chat_id, text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка habits: {e}")


def start_scheduler():
    """Запускает планировщик"""
    scheduler.add_job(morning_routine, CronTrigger(hour=8, minute=0, timezone=OWNER_TZ), id="morning_routine", replace_existing=True)
    scheduler.add_job(habits_check_job, CronTrigger(hour=9, minute=0, timezone=OWNER_TZ), id="habits_check", replace_existing=True)
    scheduler.add_job(evening_report, CronTrigger(hour=21, minute=0, timezone=OWNER_TZ), id="evening_report", replace_existing=True)
    scheduler.add_job(weekly_review_job, CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=OWNER_TZ), id="weekly_review", replace_existing=True)
    scheduler.start()
    logger.info("Планировщик: 8:00 брифинг+план, 9:00 привычки, 21:00 отчёт+энергия, вс 20:00 обзор недели")
