import logging
import re
import urllib.request
import json
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.ai import client
from bot.services import notion
from bot.config import CLAUDE_MODEL, NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


def _extract_youtube_id(text: str) -> str:
    """Извлекает ID видео из YouTube ссылки"""
    patterns = [
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _get_youtube_transcript(video_id: str) -> str:
    """Получает субтитры YouTube через бесплатный API"""
    try:
        # Пробуем получить инфо о видео через noembed
        url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", "Без названия")
            author = data.get("author_name", "")
        return title, author
    except Exception:
        return "Без названия", ""


@router.message(Command("summary"))
async def cmd_summary(message: Message):
    """
    Саммари книги, статьи или YouTube видео.
    /summary Название книги
    /summary https://youtube.com/watch?v=...
    /summary Текст статьи для конспекта
    """
    raw = message.text.replace("/summary", "", 1).strip()

    if not raw:
        await message.answer(
            "**Саммари и конспекты**\n\n"
            "/summary Название книги — саммари книги\n"
            "/summary https://youtube.com/... — саммари видео\n"
            "/summary Длинный текст — конспект текста\n\n"
            "Результат сохраняется в Notion → Саммари",
            parse_mode="Markdown",
        )
        return

    # Определяем тип контента
    youtube_id = _extract_youtube_id(raw)

    if youtube_id:
        await message.answer("Делаю саммари YouTube видео...")
        title, author = _get_youtube_transcript(youtube_id)

        prompt = f"""Сделай подробное саммари YouTube видео.

Название: {title}
Автор: {author}
Ссылка: https://youtube.com/watch?v={youtube_id}

Так как у тебя нет доступа к субтитрам, сделай саммари на основе названия и автора.
Если ты знаешь это видео или контент этого автора — используй свои знания.

Формат:
# {title}
Автор: {author}

## Ключевые идеи
- Идея 1
- Идея 2
...

## Основные тезисы
(подробнее)

## Практические выводы
- Что можно применить

## Цитаты / Запомнить
- Ключевые фразы

Если ты не знаешь содержание этого конкретного видео — честно скажи,
но предложи саммари контента этого автора по теме из названия."""

        section_icon = "🎬"
        section_title = f"YouTube: {title[:50]}"

    elif len(raw) > 200:
        # Длинный текст — конспект
        await message.answer("Делаю конспект...")
        prompt = f"""Сделай структурированный конспект текста.

ТЕКСТ:
{raw}

Формат:
# Конспект

## Главная мысль
(1-2 предложения)

## Ключевые идеи
- Идея 1
- Идея 2
...

## Детали
(важные подробности)

## Практические выводы
- Что применить"""

        section_icon = "📝"
        section_title = f"Конспект: {raw[:50]}..."

    else:
        # Название книги/статьи
        await message.answer(f"Делаю саммари: **{raw}**...", parse_mode="Markdown")
        prompt = f"""Сделай подробное саммари книги или материала.

Название: {raw}

Формат:
# {raw}

## О чём
(2-3 предложения)

## Ключевые идеи
1. Идея (подробно)
2. Идея (подробно)
...

## Лучшие цитаты
- Цитата 1
- Цитата 2

## Практические выводы
- Что применить в бизнесе
- Что применить в жизни

## Кому читать
(для кого полезна)

Если знаешь эту книгу — пиши конкретно. Если нет — честно скажи."""

        section_icon = "📖"
        section_title = raw[:60]

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text

        # Сохраняем в Notion
        notion_link = ""
        if NOTION_API_KEY:
            page = notion.add_to_section("Саммари", section_title, result, icon=section_icon)
            notion_link = f"\n\nNotion: {page['url']}"

        if len(result) > 3500:
            await message.answer(result[:3500] + "...", parse_mode=None)
            await message.answer(f"Полная версия в Notion.{notion_link}")
        else:
            await message.answer(result + notion_link, parse_mode=None)

    except Exception as e:
        logger.error(f"Ошибка саммари: {e}")
        await message.answer(f"Ошибка: {e}")
