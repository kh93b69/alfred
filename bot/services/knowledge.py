import os
import logging

logger = logging.getLogger(__name__)

# Папка с файлами базы знаний
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge")


def load_knowledge() -> str:
    """
    Загружает все .txt и .md файлы из папки knowledge/
    и склеивает их в одну строку для системного промпта.
    """
    knowledge_parts = []

    # Проверяем что папка существует
    if not os.path.exists(KNOWLEDGE_DIR):
        logger.warning(f"Папка базы знаний не найдена: {KNOWLEDGE_DIR}")
        return ""

    # Читаем все текстовые файлы
    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not filename.endswith((".txt", ".md")):
            continue

        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    # Добавляем с заголовком файла
                    name = filename.rsplit(".", 1)[0]  # убираем расширение
                    knowledge_parts.append(f"## {name}\n{content}")
                    logger.info(f"Загружен файл базы знаний: {filename}")
        except Exception as e:
            logger.error(f"Ошибка при чтении {filename}: {e}")

    if not knowledge_parts:
        logger.info("База знаний пуста")
        return ""

    return "\n\n---\n\n".join(knowledge_parts)


def add_note(title: str, content: str) -> str:
    """
    Добавляет новую заметку в базу знаний.
    Возвращает имя созданного файла.
    """
    # Очищаем имя файла от спецсимволов
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    safe_title = safe_title.strip().replace(" ", "_")
    filename = f"{safe_title}.txt"
    filepath = os.path.join(KNOWLEDGE_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Добавлена заметка: {filename}")
    return filename


def list_files() -> list[str]:
    """Возвращает список файлов в базе знаний"""
    if not os.path.exists(KNOWLEDGE_DIR):
        return []
    return [
        f for f in sorted(os.listdir(KNOWLEDGE_DIR))
        if f.endswith((".txt", ".md"))
    ]
