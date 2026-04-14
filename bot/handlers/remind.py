import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import reminders

router = Router()
logger = logging.getLogger(__name__)

# Маппинг русских дней в cron-формат
DAYS_MAP = {
    "пн": "mon", "вт": "tue", "ср": "wed", "чт": "thu",
    "пт": "fri", "сб": "sat", "вс": "sun",
    "понедельник": "mon", "вторник": "tue", "среда": "wed",
    "четверг": "thu", "пятница": "fri", "суббота": "sat", "воскресенье": "sun",
    "будни": "mon,tue,wed,thu,fri",
    "рабочие": "mon,tue,wed,thu,fri",
}


@router.message(Command("remind"))
async def cmd_remind(message: Message):
    """
    Создать напоминание.
    /remind 09:00 Выпить витамины
    /remind 08:30 будни Проверить почту
    /remind — список напоминаний
    """
    raw = message.text.replace("/remind", "", 1).strip()

    # Без аргументов — показать список
    if not raw:
        all_reminders = reminders.get_all()
        if not all_reminders:
            await message.answer(
                "Напоминаний нет.\n\n"
                "**Как добавить:**\n"
                "/remind 09:00 Выпить витамины\n"
                "/remind 08:30 будни Проверить почту\n"
                "/remind 22:00 Записать итоги дня\n\n"
                "**Дни:** будни, пн, вт, ср, чт, пт, сб, вс\n"
                "Без указания дня — каждый день.",
                parse_mode="Markdown",
            )
            return

        text = "🔔 **Твои напоминания:**\n\n"
        for r in all_reminders:
            days_label = "ежедневно" if r.get("days", "daily") == "daily" else r["days"]
            text += f"#{r['id']} — **{r['time']}** ({days_label})\n  {r['text']}\n\n"
        text += "Удалить: /forget номер (например /forget 1)"
        await message.answer(text, parse_mode="Markdown")
        return

    # Парсим: время, [дни], текст
    parts = raw.split()
    if len(parts) < 2:
        await message.answer("Формат: /remind 09:00 Текст напоминания")
        return

    # Первый аргумент — время
    time_str = parts[0]
    if ":" not in time_str:
        await message.answer("Укажи время в формате ЧЧ:ММ (например 09:00)")
        return

    # Проверяем валидность времени
    try:
        h, m = map(int, time_str.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        await message.answer("Неверный формат времени. Используй ЧЧ:ММ (например 09:00)")
        return

    # Второй аргумент — может быть день недели или уже текст
    days = "daily"
    text_start = 1

    if len(parts) > 2 and parts[1].lower() in DAYS_MAP:
        days = DAYS_MAP[parts[1].lower()]
        text_start = 2
    elif len(parts) > 2 and "," in parts[1]:
        # Попробуем распарсить как список дней: "пн,ср,пт"
        day_parts = parts[1].lower().split(",")
        cron_days = []
        for d in day_parts:
            if d.strip() in DAYS_MAP:
                cron_days.append(DAYS_MAP[d.strip()])
        if cron_days:
            days = ",".join(cron_days)
            text_start = 2

    reminder_text = " ".join(parts[text_start:])
    if not reminder_text:
        await message.answer("Укажи текст напоминания.")
        return

    # Создаём напоминание
    r = reminders.add_reminder(text=reminder_text, time=time_str, days=days)
    days_label = "ежедневно" if days == "daily" else days

    await message.answer(
        f"✅ Напоминание #{r['id']} создано:\n\n"
        f"🔔 **{time_str}** ({days_label})\n"
        f"{reminder_text}",
        parse_mode="Markdown",
    )


@router.message(Command("forget"))
async def cmd_forget(message: Message):
    """Удалить напоминание: /forget 1"""
    raw = message.text.replace("/forget", "", 1).strip()

    if not raw:
        await message.answer("Формат: /forget номер\nПосмотреть список: /remind")
        return

    try:
        reminder_id = int(raw)
    except ValueError:
        await message.answer("Укажи номер напоминания (число).")
        return

    if reminders.remove_reminder(reminder_id):
        await message.answer(f"Напоминание #{reminder_id} удалено.")
    else:
        await message.answer(f"Напоминание #{reminder_id} не найдено.")
