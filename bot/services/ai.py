import anthropic
import logging
from bot.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_HISTORY_LENGTH
from bot.services.knowledge import load_knowledge

logger = logging.getLogger(__name__)

# Клиент Claude API
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Базовый системный промпт — личность Альфреда
BASE_PROMPT = """Ты — Альфред, персональный AI-ассистент и "второй мозг".

Твоя роль:
- Ты помогаешь своему владельцу управлять бизнесом, проектами и задачами
- Ты умный, проактивный и деловой
- Ты отвечаешь конкретно, без воды
- Ты всегда общаешься на русском языке
- Ты обращаешься к владельцу на "ты"
- Ты предлагаешь идеи и решения, а не просто отвечаешь на вопросы

Стиль общения:
- Краткий и по делу, как хороший исполнительный помощник
- Используешь структурированные ответы (списки, пункты) когда уместно
- Если владелец даёт задачу — подтверждаешь и уточняешь детали если нужно
- Если видишь возможность улучшить процесс — предлагаешь

Пока у тебя нет доступа к внешним сервисам (Trello, Notion), но скоро будет.
Сейчас ты можешь: отвечать на вопросы, помогать думать, планировать, генерировать идеи."""

# Хранилище истории диалогов (ключ — ID чата в Telegram)
chat_histories: dict[int, list[dict]] = {}


def build_system_prompt() -> str:
    """Собирает системный промпт с базой знаний"""
    knowledge = load_knowledge()

    if knowledge:
        return (
            f"{BASE_PROMPT}\n\n"
            f"# БАЗА ЗНАНИЙ ВЛАДЕЛЬЦА\n"
            f"Ниже — информация о проектах, целях и планах владельца. "
            f"Используй эти знания при ответах. Ссылайся на них когда уместно.\n\n"
            f"{knowledge}"
        )

    return BASE_PROMPT


def get_history(chat_id: int) -> list[dict]:
    """Получить историю диалога для конкретного чата"""
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    return chat_histories[chat_id]


async def ask_alfred(chat_id: int, user_message: str) -> str:
    """Отправить сообщение Альфреду и получить ответ"""

    # Получаем историю диалога
    history = get_history(chat_id)

    # Добавляем новое сообщение пользователя
    history.append({"role": "user", "content": user_message})

    # Обрезаем историю если она слишком длинная
    if len(history) > MAX_HISTORY_LENGTH:
        history[:] = history[-MAX_HISTORY_LENGTH:]

    # Собираем промпт с актуальной базой знаний
    system_prompt = build_system_prompt()

    # Отправляем запрос в Claude API
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=history,
    )

    # Достаём текст ответа
    assistant_message = response.content[0].text

    # Сохраняем ответ в историю
    history.append({"role": "assistant", "content": assistant_message})

    return assistant_message
