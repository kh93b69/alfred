import logging
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.ai import client
from bot.services.knowledge import load_knowledge
from bot.services import trello, task_memory, notion
from bot.config import CLAUDE_MODEL, TRELLO_LIST_DONE, NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("weekly"))
async def cmd_weekly(message: Message):
    """Еженедельный обзор: анализ недели + корректировка планов"""
    await message.answer("Делаю еженедельный обзор... Это займёт минуту.")

    try:
        # Собираем данные
        knowledge = load_knowledge()[:5000]

        # Выполненные задачи за неделю (из task_memory)
        memory = task_memory._load()
        completed = memory.get("completed", [])
        rejected = memory.get("rejected", [])

        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        completed_week = [c for c in completed if c.get("date", "") >= week_ago]
        rejected_week = [r for r in rejected if r.get("date", "") >= week_ago]

        # Энергия за неделю
        try:
            from bot.handlers.energy import _load as load_energy
            energy_data = load_energy()
            energy_week = [e for e in energy_data if e.get("date", "") >= week_ago]
            energy_avg = sum(e["score"] for e in energy_week) / len(energy_week) if energy_week else 0
        except Exception:
            energy_avg = 0
            energy_week = []

        # TickTick задачи
        ticktick_summary = ""
        try:
            from bot.services import ticktick
            if ticktick.is_connected():
                tt_tasks = ticktick.get_all_tasks()
                tt_active = [t for t in tt_tasks if t.get("status", 0) != 2]
                ticktick_summary = f"{len(tt_active)} активных в TickTick"
        except Exception:
            pass

        # Задачи Trello
        trello_cards = trello.get_cards()
        trello_summary = f"{len(trello_cards)} на доске Trello"

        # Формируем промпт
        prompt = f"""Ты — Альфред. Сделай еженедельный обзор для владельца.

БАЗА ЗНАНИЙ (цели и стратегия):
{knowledge if knowledge else "Нет данных"}

ДАННЫЕ ЗА НЕДЕЛЮ:

✅ Выполнено задач: {len(completed_week)}
{chr(10).join(f'  - {c["name"]}' for c in completed_week[:20])}

❌ Отклонено: {len(rejected_week)}
{chr(10).join(f'  - {r["name"]}' for r in rejected_week[:10])}

⚡ Средняя энергия: {energy_avg:.1f}/10 ({len(energy_week)} замеров)

📋 Текущие задачи: {trello_summary}, {ticktick_summary}

Сделай обзор в формате:

# 📊 Еженедельный обзор ({datetime.now().strftime('%d.%m.%Y')})

## ✅ Что удалось
(3-5 ключевых достижений недели с контекстом)

## 📉 Что не получилось
(что застопорилось, почему, что с этим делать)

## ⚡ Энергия и продуктивность
(анализ — когда был наиболее продуктивен, паттерны)

## 🎯 Прогресс к целям
(анализируй на основе базы знаний — насколько продвинулся к главным целям)

## 💡 Рекомендации на следующую неделю
(3-5 конкретных фокусов на следующие 7 дней)

## ⚠️ Красные флаги
(на что обратить внимание, где есть риск срыва)

Будь честным и конкретным. Без воды."""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text

        # Сохраняем в Notion
        notion_link = ""
        if NOTION_API_KEY:
            try:
                title = f"Обзор недели {datetime.now().strftime('%d.%m.%Y')}"
                page = notion.add_to_section("Саммари", title, result, icon="📊")
                notion_link = f"\n\nNotion: {page['url']}"
            except Exception as e:
                logger.error(f"Ошибка Notion: {e}")

        if len(result) > 3500:
            await message.answer(result[:3500] + "...", parse_mode=None)
            await message.answer(f"Полный обзор в Notion.{notion_link}")
        else:
            await message.answer(result + notion_link, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка weekly: {e}")
        await message.answer(f"Ошибка: {e}")
