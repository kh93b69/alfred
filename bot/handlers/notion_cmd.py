import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import notion
from bot.services.ai import client
from bot.config import CLAUDE_MODEL, NOTION_API_KEY

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("notion"))
async def cmd_notion(message: Message):
    """Показать разделы Notion или создать страницу"""
    if not NOTION_API_KEY:
        await message.answer("Notion не настроен. Добавь NOTION_API_KEY в переменные.")
        return

    raw = message.text.replace("/notion", "", 1).strip()

    # Без аргументов — показать разделы
    if not raw:
        try:
            sections = notion.ensure_sections()
            text = "📓 **Notion — Разделы Альфреда:**\n\n"
            for name, page_id in sections.items():
                icon = notion.SECTION_STRUCTURE.get(name, "📄")
                text += f"{icon} {name}\n"
            text += (
                "\n**Как использовать:**\n"
                "/notion регламент Название | Текст\n"
                "/notion саммари Название | Текст\n"
                "/notion заметка Название | Текст\n\n"
                "Или скинь ссылку на YouTube — я сделаю саммари."
            )
            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
        return

    # Парсим: тип | название | контент
    # Формат: /notion регламент Название | Текст
    parts = raw.split("|", 1)
    if len(parts) < 2:
        await message.answer(
            "Формат: /notion тип Название | Текст\n\n"
            "Типы: регламент, саммари, заметка, идея, контакт\n\n"
            "Пример:\n/notion регламент Работа с CRM | Все менеджеры обязаны..."
        )
        return

    header = parts[0].strip()
    content = parts[1].strip()

    # Определяем раздел и название
    section_map = {
        "регламент": "Регламенты",
        "саммари": "Саммари",
        "заметка": "База знаний",
        "знание": "База знаний",
        "идея": "Идеи",
        "контакт": "Контакты",
        "цель": "Цели",
    }

    # Первое слово — тип, остальное — название
    words = header.split(maxsplit=1)
    section_key = words[0].lower() if words else ""
    title = words[1] if len(words) > 1 else header

    section_name = section_map.get(section_key, "База знаний")
    if section_key not in section_map:
        title = header  # если тип не распознан — всё идёт в название

    await message.answer(f"Сохраняю в Notion → {section_name}...")

    try:
        page = notion.add_to_section(section_name, title, content)
        await message.answer(
            f"✅ Сохранено в **{section_name}**:\n\n"
            f"**{title}**\n"
            f"Ссылка: {page['url']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Ошибка Notion: {e}")
        await message.answer(f"Ошибка: {e}")


@router.message(Command("reg"))
async def cmd_reg(message: Message):
    """
    Быстрое создание регламента.
    /reg Название | Описание процесса в свободной форме
    Альфред сам структурирует в полноценный регламент.
    """
    if not NOTION_API_KEY:
        await message.answer("Notion не настроен.")
        return

    raw = message.text.replace("/reg", "", 1).strip()

    if not raw or "|" not in raw:
        await message.answer(
            "Формат: /reg Название | Описание процесса\n\n"
            "Пример:\n"
            "/reg Работа с клиентами | Менеджер получает заявку, связывается в течение часа, "
            "уточняет потребности, отправляет КП, контролирует оплату"
        )
        return

    title, description = raw.split("|", 1)
    title = title.strip()
    description = description.strip()

    await message.answer(f"Пишу регламент: **{title}**...", parse_mode="Markdown")

    try:
        # Claude структурирует в регламент
        prompt = f"""Напиши структурированный регламент на основе описания.

Название: {title}
Описание: {description}

Формат регламента:
# {title}

## Цель
(зачем нужен этот регламент)

## Область применения
(кто и когда использует)

## Порядок действий
1. Шаг 1
2. Шаг 2
...

## Ответственные
(кто за что отвечает)

## Контроль
(как проверять выполнение)

Пиши конкретно и по делу, без воды."""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        reg_content = response.content[0].text

        # Сохраняем в Notion
        page = notion.add_to_section("Регламенты", title, reg_content, icon="📋")

        await message.answer(
            f"✅ Регламент готов: **{title}**\n\n"
            f"Ссылка: {page['url']}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"Ошибка: {e}")
