import logging
from aiogram import Router
from aiogram.types import Message

from bot.services.ai import ask_alfred

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def handle_text(message: Message):
    """Обработчик всех текстовых сообщений — отправляем Альфреду"""

    # Игнорируем пустые сообщения
    if not message.text:
        return

    logger.info(f"Сообщение от {message.from_user.full_name}: {message.text[:50]}...")

    # Показываем что бот печатает
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Получаем ответ от Альфреда
        response = await ask_alfred(
            chat_id=message.chat.id,
            user_message=message.text,
        )
        await message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка при обращении к Claude API: {e}")
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуй ещё раз через пару секунд."
        )
