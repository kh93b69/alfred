import os
import logging
import tempfile
from aiogram import Router
from aiogram.types import Message
from openai import OpenAI

from bot.config import OPENAI_API_KEY
from bot.handlers.chat import _detect_and_execute

router = Router()
logger = logging.getLogger(__name__)

# Клиент OpenAI (только для Whisper)
openai_client = None


def get_openai_client():
    """Получить клиент OpenAI (создаём лениво)"""
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return openai_client


async def transcribe_voice(bot, file_id: str) -> str:
    """Скачивает голосовое сообщение и транскрибирует через Whisper"""
    # Скачиваем файл из Telegram
    file = await bot.get_file(file_id)

    # Создаём временный файл
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
        await bot.download_file(file.file_path, tmp_path)

    try:
        # Отправляем в Whisper API
        client = get_openai_client()
        with open(tmp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
            )
        return result.text
    finally:
        # Удаляем временный файл
        os.unlink(tmp_path)


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message):
    """Обработчик голосовых сообщений"""
    if not OPENAI_API_KEY:
        await message.answer("OpenAI API ключ не настроен. Голосовые пока не работают.")
        return

    await message.answer("Слушаю...")

    try:
        # Транскрибируем голосовое
        text = await transcribe_voice(message.bot, message.voice.file_id)

        if not text.strip():
            await message.answer("Не удалось распознать речь. Попробуй ещё раз.")
            return

        logger.info(f"Распознано голосовое от {message.from_user.full_name}: {text[:50]}...")

        # Показываем что распознали
        await message.answer(f"📝 Распознано:\n_{text}_", parse_mode="Markdown")

        # Отправляем в умный роутинг (как текстовое сообщение)
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        await _detect_and_execute(message, text)

    except Exception as e:
        logger.error(f"Ошибка обработки голосового: {e}")
        await message.answer(f"Ошибка при распознавании голосового: {e}")


@router.message(lambda m: m.video_note is not None)
async def handle_video_note(message: Message):
    """Обработчик кружочков (видео-заметок)"""
    if not OPENAI_API_KEY:
        await message.answer("OpenAI API ключ не настроен.")
        return

    await message.answer("Слушаю кружочек...")

    try:
        text = await transcribe_voice(message.bot, message.video_note.file_id)

        if not text.strip():
            await message.answer("Не удалось распознать речь.")
            return

        await message.answer(f"📝 Распознано:\n_{text}_", parse_mode="Markdown")

        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        await _detect_and_execute(message, text)

    except Exception as e:
        logger.error(f"Ошибка обработки кружочка: {e}")
        await message.answer(f"Ошибка при распознавании: {e}")
