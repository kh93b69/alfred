import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services import habits

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("habit"))
async def cmd_habit(message: Message):
    """
    Управление привычками.
    /habit — показать все + отметить
    /habit add 09:00 Пить витамины — добавить
    /habit remove 1 — удалить
    """
    raw = message.text.replace("/habit", "", 1).strip()

    # Добавление
    if raw.startswith("add ") or raw.startswith("добавить "):
        args = raw.replace("add ", "", 1).replace("добавить ", "", 1).strip()
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Формат: /habit add 09:00 Название привычки")
            return
        time_str, name = parts

        # Проверяем время
        if ":" not in time_str:
            await message.answer("Неверное время. Формат: ЧЧ:ММ")
            return

        habit = habits.add_habit(name, time_str)
        await message.answer(f"✅ Привычка добавлена: **{name}** в {time_str}", parse_mode="Markdown")
        return

    # Удаление
    if raw.startswith("remove ") or raw.startswith("удалить "):
        args = raw.replace("remove ", "", 1).replace("удалить ", "", 1).strip()
        try:
            habit_id = int(args)
        except ValueError:
            await message.answer("Укажи номер привычки")
            return
        if habits.remove_habit(habit_id):
            await message.answer(f"Привычка #{habit_id} удалена")
        else:
            await message.answer("Привычка не найдена")
        return

    # Статистика
    if raw in ("stats", "статистика"):
        all_habits = habits.get_habits()
        if not all_habits:
            await message.answer("Привычек нет.")
            return

        text = "📊 **Статистика привычек (30 дней):**\n\n"
        for h in all_habits:
            stats = habits.get_stats(h["id"], days=30)
            percent = int(stats["total_days"] / 30 * 100)
            bar = "🟩" * (percent // 10) + "⬜" * (10 - percent // 10)
            text += f"**{h['name']}**\n"
            text += f"{bar} {percent}% ({stats['total_days']}/30)\n"
            text += f"🔥 Streak: {stats['streak']} дней\n\n"
        await message.answer(text, parse_mode="Markdown")
        return

    # Показать список с кнопками отметки
    all_habits = habits.get_habits()
    if not all_habits:
        await message.answer(
            "У тебя пока нет привычек.\n\n"
            "**Добавить:**\n"
            "/habit add 09:00 Пить витамины\n"
            "/habit add 22:00 Прочитать 10 страниц\n\n"
            "**Другие команды:**\n"
            "/habit stats — статистика\n"
            "/habit remove 1 — удалить",
            parse_mode="Markdown",
        )
        return

    text = f"🌱 **Твои привычки ({datetime.now().strftime('%d.%m.%Y')}):**\n\n"
    for h in all_habits:
        streak = habits.get_streak(h["id"])
        text += f"#{h['id']} **{h['name']}** ({h.get('time', '09:00')}) 🔥 {streak} дней\n"

    text += "\nОтметь сегодняшние:"

    # Кнопки для каждой привычки
    buttons = []
    for h in all_habits:
        row = [
            InlineKeyboardButton(text=f"✅ {h['name'][:25]}", callback_data=f"habit_yes:{h['id']}"),
            InlineKeyboardButton(text=f"❌", callback_data=f"habit_no:{h['id']}"),
        ]
        buttons.append(row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data.startswith("habit_yes:"))
async def on_habit_yes(callback: CallbackQuery):
    """Привычка выполнена"""
    habit_id = int(callback.data.replace("habit_yes:", ""))
    habits.check_habit(habit_id, done=True)

    # Находим привычку
    habit = next((h for h in habits.get_habits() if h["id"] == habit_id), None)
    if habit:
        streak = habits.get_streak(habit_id)
        await callback.answer(f"✅ {habit['name']} — streak {streak} дней!", show_alert=False)
    else:
        await callback.answer("Отмечено")


@router.callback_query(F.data.startswith("habit_no:"))
async def on_habit_no(callback: CallbackQuery):
    """Привычка пропущена"""
    habit_id = int(callback.data.replace("habit_no:", ""))
    habits.check_habit(habit_id, done=False)
    await callback.answer("Пропустил — не страшно, завтра получится")
