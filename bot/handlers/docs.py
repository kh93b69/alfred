import os
import json
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from bot.services.documents import list_templates, get_template_fields, fill_template
from bot.services.ai import client
from bot.config import CLAUDE_MODEL

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("doc"))
async def cmd_doc(message: Message):
    """
    Генерация документа из шаблона.
    Формат: /doc шаблон | реквизиты в свободной форме
    Или просто /doc — покажет список шаблонов
    """
    raw = message.text.replace("/doc", "", 1).strip()

    # Если без аргументов — показываем список шаблонов
    if not raw:
        templates = list_templates()
        if not templates:
            await message.answer("Шаблоны не найдены. Они создаются автоматически при перезапуске.")
            return

        text = "📄 **Доступные шаблоны:**\n\n"
        for i, t in enumerate(templates, 1):
            name = t.rsplit(".", 1)[0]
            fields = get_template_fields(t)
            text += f"{i}. **{name}**\n"
            text += f"   Поля: {', '.join(fields[:5])}...\n\n"

        text += (
            "**Как использовать:**\n"
            "/doc договор | ООО Рога и Копыта, ИНН 1234567890, "
            "услуги по разработке сайта, сумма 150000 руб...\n\n"
            "Просто напиши реквизиты в свободной форме — я сам разберусь что куда подставить."
        )
        await message.answer(text, parse_mode="Markdown")
        return

    # Парсим шаблон и реквизиты
    if "|" not in raw:
        await message.answer(
            "Формат: /doc шаблон | реквизиты\n\n"
            "Пример:\n"
            "/doc договор | Исполнитель: ООО Альфа, ИНН 123456, "
            "Заказчик: ИП Иванов, услуги консалтинга, 200000 руб"
        )
        return

    template_query, requisites = raw.split("|", 1)
    template_query = template_query.strip().lower()
    requisites = requisites.strip()

    # Ищем подходящий шаблон
    templates = list_templates()
    matched = None
    for t in templates:
        if template_query in t.lower():
            matched = t
            break

    if not matched:
        await message.answer(
            f"Шаблон '{template_query}' не найден.\n"
            f"Доступные: {', '.join(templates)}"
        )
        return

    await message.answer(f"Генерирую документ из шаблона **{matched}**...", parse_mode="Markdown")

    try:
        # Получаем поля шаблона
        fields = get_template_fields(matched)

        # Просим Claude распарсить реквизиты
        parse_prompt = (
            f"Из текста ниже извлеки данные для заполнения документа.\n"
            f"Поля которые нужно заполнить: {', '.join(fields)}\n\n"
            f"Текст с реквизитами:\n{requisites}\n\n"
            f"Верни ТОЛЬКО JSON объект без markdown-разметки, где ключи — точные названия полей, "
            f"значения — извлечённые данные. Если поле невозможно определить из текста, "
            f"поставь прочерк '—'. Не добавляй никакого текста кроме JSON."
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": parse_prompt}],
        )

        # Парсим JSON из ответа
        json_text = response.content[0].text.strip()
        # Убираем возможные markdown-блоки
        if json_text.startswith("```"):
            json_text = json_text.split("\n", 1)[1]
            json_text = json_text.rsplit("```", 1)[0]

        data = json.loads(json_text)
        logger.info(f"Claude распарсил реквизиты: {list(data.keys())}")

        # Заполняем шаблон
        output_path = fill_template(matched, data)

        # Отправляем файл пользователю
        doc_file = FSInputFile(output_path)
        await message.answer_document(
            doc_file,
            caption=f"Документ готов: **{matched.rsplit('.', 1)[0]}**",
            parse_mode="Markdown",
        )

        # Удаляем временный файл
        os.remove(output_path)

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON от Claude: {e}")
        await message.answer("Не удалось распарсить реквизиты. Попробуй написать их подробнее.")
    except Exception as e:
        logger.error(f"Ошибка генерации документа: {e}")
        await message.answer(f"Ошибка при генерации: {e}")
