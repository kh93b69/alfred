import json
import os
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
logger = logging.getLogger(__name__)

OWNER_TZ = timezone(timedelta(hours=5))
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "energy.json")


def _ensure_dir():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def _load() -> list[dict]:
    _ensure_dir()
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]):
    _ensure_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.message(Command("energy"))
async def cmd_energy(message: Message):
    """Энергетическая карта — трекинг энергии"""
    raw = message.text.replace("/energy", "", 1).strip()

    # Если /energy stats — показать статистику
    if raw == "stats" or raw == "стат":
        data = _load()
        if len(data) < 3:
            await message.answer("Недостаточно данных. Отмечай энергию хотя бы 3 дня.")
            return

        # Анализ
        last_7 = data[-7:] if len(data) >= 7 else data
        last_30 = data[-30:] if len(data) >= 30 else data

        avg_7 = sum(d["score"] for d in last_7) / len(last_7)
        avg_all = sum(d["score"] for d in last_30) / len(last_30)

        # Паттерны по дням недели
        by_weekday: dict[str, list] = {}
        for d in last_30:
            wd = d.get("weekday", "")
            if wd:
                if wd not in by_weekday:
                    by_weekday[wd] = []
                by_weekday[wd].append(d["score"])

        text = "⚡ **Энергетическая карта:**\n\n"
        text += f"Средняя за 7 дней: **{avg_7:.1f}/10**\n"
        text += f"Средняя за всё время: **{avg_all:.1f}/10**\n\n"

        if by_weekday:
            text += "**По дням недели:**\n"
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for day in days_order:
                scores = by_weekday.get(day, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    bar = "🟩" * round(avg) + "⬜" * (10 - round(avg))
                    text += f"{day}: {bar} {avg:.1f}\n"

        text += f"\nЗаписей: {len(data)}"

        # Тренд
        if len(data) >= 7:
            first_half = sum(d["score"] for d in last_7[:len(last_7)//2]) / (len(last_7)//2)
            second_half = sum(d["score"] for d in last_7[len(last_7)//2:]) / (len(last_7) - len(last_7)//2)
            if second_half > first_half + 0.5:
                text += "\n📈 Тренд: энергия растёт!"
            elif second_half < first_half - 0.5:
                text += "\n📉 Тренд: энергия падает. Обрати внимание на отдых."
            else:
                text += "\n➡️ Тренд: стабильно"

        await message.answer(text, parse_mode="Markdown")
        return

    # Показать кнопки для оценки энергии
    buttons = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"energy:{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "⚡ **Как твоя энергия сейчас?**\n"
        "1 = полный ноль, 10 = на максимуме",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("energy:"))
async def on_energy(callback: CallbackQuery):
    """Сохранение уровня энергии"""
    score = int(callback.data.replace("energy:", ""))
    await callback.answer(f"Записал: {score}/10")

    now = datetime.now(OWNER_TZ)
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": weekdays[now.weekday()],
        "score": score,
    }

    data = _load()
    data.append(entry)
    _save(data)

    emoji = "🔋" if score >= 7 else "🪫" if score <= 3 else "⚡"
    await callback.message.edit_text(
        f"{emoji} Энергия: **{score}/10** ({now.strftime('%H:%M')})\n\n"
        f"Статистика: /energy stats",
        parse_mode="Markdown",
    )
