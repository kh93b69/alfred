import os
import json
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from bot.services.invoice import generate_invoice
from bot.services.ai import client
from bot.config import CLAUDE_MODEL

router = Router()
logger = logging.getLogger(__name__)

INVOICE_FIELDS = [
    "НОМЕР_СЧЁТА",
    "ДАТА_СЧЁТА",
    "ПОКУПАТЕЛЬ_БИН",
    "ПОКУПАТЕЛЬ_НАЗВАНИЕ",
    "ПОКУПАТЕЛЬ_АДРЕС",
    "НОМЕР_ДОГОВОРА",
    "НАЗВАНИЕ_ДОГОВОРА",
    "НАИМЕНОВАНИЕ_УСЛУГИ",
    "СУММА",
]


@router.message(Command("invoice"))
async def cmd_invoice(message: Message):
    """
    Генерация счёта на оплату ИП Knyaz.
    Формат: /invoice реквизиты покупателя и детали в свободной форме
    """
    raw = message.text.replace("/invoice", "", 1).strip()

    if not raw:
        await message.answer(
            "**Счёт на оплату ИП Knyaz**\n\n"
            "Формат: /invoice данные в свободной форме\n\n"
            "Пример:\n"
            "/invoice Счёт 15 от 10 апреля 2026, покупатель ТОО YURT HOLDING "
            "БИН 240140011394, Туркестан ул. Алмалы 31, "
            "договор возмездного оказания услуг №67, "
            "рекламные услуги, 69990 тенге\n\n"
            "Просто напиши данные — я сам разберусь что куда подставить.",
            parse_mode="Markdown",
        )
        return

    await message.answer("Генерирую счёт...")

    try:
        # Просим Claude распарсить реквизиты
        parse_prompt = (
            f"Из текста ниже извлеки данные для счёта на оплату.\n"
            f"Нужные поля: {', '.join(INVOICE_FIELDS)}\n\n"
            f"Текст:\n{raw}\n\n"
            f"НАЗВАНИЕ_ДОГОВОРА — тип договора (например 'ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ УСЛУГ'). "
            f"Если не указано, используй 'ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ УСЛУГ'.\n"
            f"СУММА — только число, без валюты.\n"
            f"ДАТА_СЧЁТА — в формате 'DD месяц YYYY г.' (например '6 апреля 2026 г.').\n\n"
            f"Верни ТОЛЬКО JSON без markdown-разметки. "
            f"Если поле не указано — поставь прочерк '—'."
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": parse_prompt}],
        )

        json_text = response.content[0].text.strip()
        if json_text.startswith("```"):
            json_text = json_text.split("\n", 1)[1]
            json_text = json_text.rsplit("```", 1)[0]

        data = json.loads(json_text)
        logger.info(f"Распарсены данные счёта: {data}")

        # Генерируем документ
        output_path = generate_invoice(data)

        # Отправляем файл
        doc_file = FSInputFile(output_path)
        номер = data.get("НОМЕР_СЧЁТА", "—")
        покупатель = data.get("ПОКУПАТЕЛЬ_НАЗВАНИЕ", "—")

        await message.answer_document(
            doc_file,
            caption=(
                f"Счёт на оплату №{номер}\n"
                f"Покупатель: {покупатель}\n"
                f"Сумма: {data.get('СУММА', '—')} KZT"
            ),
        )

        # Удаляем файл после отправки
        os.remove(output_path)

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга: {e}")
        await message.answer("Не удалось распарсить данные. Напиши подробнее.")
    except Exception as e:
        logger.error(f"Ошибка генерации счёта: {e}")
        await message.answer(f"Ошибка: {e}")
