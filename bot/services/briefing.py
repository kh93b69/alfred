import json
import logging
import urllib.request
from datetime import datetime, timezone, timedelta

from bot.services import trello
from bot.services.knowledge import load_knowledge
from bot.config import TRELLO_LIST_INBOX, TRELLO_LIST_DOING

logger = logging.getLogger(__name__)
OWNER_TZ = timezone(timedelta(hours=5))


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Безопасный GET-запрос"""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Alfred-Bot/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Не удалось загрузить {url}: {e}")
        return {}


def get_weather() -> str:
    """Погода в Караганде"""
    data = _fetch_json("https://wttr.in/Karaganda?format=j1")
    if not data:
        return "Погода: данные недоступны"

    try:
        current = data["current_condition"][0]
        temp = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc_ru = current.get("lang_ru", [{}])
        desc = desc_ru[0].get("value", current.get("weatherDesc", [{}])[0].get("value", ""))
        humidity = current["humidity"]
        return f"🌡 Караганда: {temp}°C (ощущается {feels}°C), {desc}, влажность {humidity}%"
    except (KeyError, IndexError):
        return "Погода: не удалось разобрать данные"


def get_currency() -> str:
    """Курсы валют KZT"""
    # Используем бесплатный API
    data = _fetch_json("https://open.er-api.com/v6/latest/USD")
    if not data or "rates" not in data:
        return "Курсы валют: данные недоступны"

    try:
        kzt = data["rates"].get("KZT", 0)
        rub = data["rates"].get("RUB", 0)
        eur_rate = data["rates"].get("EUR", 0)

        # USD → KZT, EUR → KZT, RUB → KZT
        eur_kzt = kzt / eur_rate if eur_rate else 0
        rub_kzt = kzt / rub if rub else 0

        return (
            f"💱 Курсы:\n"
            f"  USD/KZT: {kzt:.0f} ₸\n"
            f"  EUR/KZT: {eur_kzt:.0f} ₸\n"
            f"  RUB/KZT: {rub_kzt:.2f} ₸"
        )
    except Exception:
        return "Курсы валют: ошибка расчёта"


def get_tasks_summary() -> str:
    """Сводка по задачам"""
    try:
        cards = trello.get_cards()
        inbox = [c for c in cards if c["idList"] == TRELLO_LIST_INBOX]
        doing = [c for c in cards if c["idList"] == TRELLO_LIST_DOING]

        text = f"📋 Задачи: {len(inbox)} входящих, {len(doing)} в работе"
        if doing:
            text += "\n  В работе:"
            for c in doing[:3]:
                text += f"\n  • {c['name']}"
        return text
    except Exception:
        return "Задачи: не удалось загрузить"


async def build_morning_briefing() -> str:
    """Собирает утренний брифинг"""
    now = datetime.now(OWNER_TZ)
    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = weekdays[now.weekday()]

    briefing = f"🌅 **Доброе утро! {day_name}, {now.strftime('%d.%m.%Y')}**\n\n"

    # Погода
    briefing += get_weather() + "\n\n"

    # Курсы валют
    briefing += get_currency() + "\n\n"

    # Задачи
    briefing += get_tasks_summary() + "\n\n"

    # Мотивация на день
    briefing += "---\nГотов к продуктивному дню? Напиши /plan для планирования."

    return briefing
