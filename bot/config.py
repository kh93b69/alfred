import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен Telegram-бота (получаем у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Ключ API Anthropic (Claude)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Ключ API OpenAI (для Whisper — распознавание голоса)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Модель Claude для использования
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Notion
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_ROOT_PAGE_ID = os.getenv("NOTION_ROOT_PAGE_ID")

# TickTick
TICKTICK_CLIENT_ID = os.getenv("TICKTICK_CLIENT_ID")
TICKTICK_CLIENT_SECRET = os.getenv("TICKTICK_CLIENT_SECRET")

# Trello
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")

# ID списков на доске Trello
TRELLO_LIST_INBOX = os.getenv("TRELLO_LIST_INBOX")       # Входящие
TRELLO_LIST_DOING = os.getenv("TRELLO_LIST_DOING")       # В работе
TRELLO_LIST_REVIEW = os.getenv("TRELLO_LIST_REVIEW")     # На проверку
TRELLO_LIST_DONE = os.getenv("TRELLO_LIST_DONE")         # Готово

# Максимальное количество сообщений в истории диалога (чтобы не тратить токены)
MAX_HISTORY_LENGTH = 20
