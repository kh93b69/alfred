import logging
import os
import urllib.request
import urllib.parse
import json

from bot.config import (
    TRELLO_API_KEY,
    TRELLO_TOKEN,
    TRELLO_BOARD_ID,
    TRELLO_LIST_INBOX,
    TRELLO_LIST_DOING,
    TRELLO_LIST_REVIEW,
    TRELLO_LIST_DONE,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.trello.com/1"


def _request(method: str, path: str, params: dict = None) -> dict:
    """Выполняет запрос к Trello API"""
    if params is None:
        params = {}

    # Добавляем ключ и токен к каждому запросу
    params["key"] = TRELLO_API_KEY
    params["token"] = TRELLO_TOKEN

    url = f"{BASE_URL}{path}"

    if method == "GET":
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
        req = urllib.request.Request(url)
    else:
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def create_card(name: str, description: str = "", list_id: str = None) -> dict:
    """
    Создаёт карточку в Trello.
    По умолчанию кладёт в список 'Входящие'.
    """
    if list_id is None:
        list_id = TRELLO_LIST_INBOX

    result = _request("POST", "/cards", {
        "name": name,
        "desc": description,
        "idList": list_id,
    })
    logger.info(f"Создана карточка: {name} (id: {result['id']})")
    return result


def move_card(card_id: str, list_id: str) -> dict:
    """Перемещает карточку в другой список"""
    result = _request("PUT", f"/cards/{card_id}", {"idList": list_id})
    logger.info(f"Карточка {card_id} перемещена в {list_id}")
    return result


def add_comment(card_id: str, text: str) -> dict:
    """Добавляет комментарий к карточке"""
    return _request("POST", f"/cards/{card_id}/actions/comments", {"text": text})


def get_cards(list_id: str = None) -> list[dict]:
    """Получает карточки из списка. Без аргумента — все карточки с доски."""
    if list_id:
        return _request("GET", f"/lists/{list_id}/cards")
    return _request("GET", f"/boards/{TRELLO_BOARD_ID}/cards")


def get_lists() -> list[dict]:
    """Получает все списки с доски"""
    return _request("GET", f"/boards/{TRELLO_BOARD_ID}/lists")


# Удобные функции для перемещения по колонкам
def move_to_doing(card_id: str) -> dict:
    return move_card(card_id, TRELLO_LIST_DOING)


def move_to_review(card_id: str) -> dict:
    return move_card(card_id, TRELLO_LIST_REVIEW)


def move_to_done(card_id: str) -> dict:
    return move_card(card_id, TRELLO_LIST_DONE)


def attach_file(card_id: str, filepath: str, filename: str = None) -> dict:
    """Прикрепляет файл к карточке Trello"""
    import mimetypes

    if filename is None:
        filename = os.path.basename(filepath)

    content_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"

    # Trello требует multipart/form-data для загрузки файлов
    boundary = "----AlfredBoundary"
    body = b""

    # Поле key
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="key"\r\n\r\n{TRELLO_API_KEY}\r\n'.encode()

    # Поле token
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="token"\r\n\r\n{TRELLO_TOKEN}\r\n'.encode()

    # Поле name
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="name"\r\n\r\n{filename}\r\n'.encode()

    # Файл
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += f"Content-Type: {content_type}\r\n\r\n".encode()
    with open(filepath, "rb") as f:
        body += f.read()
    body += f"\r\n--{boundary}--\r\n".encode()

    url = f"{BASE_URL}/cards/{card_id}/attachments"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))

    logger.info(f"Файл {filename} прикреплён к карточке {card_id}")
    return result


def delete_card(card_id: str) -> None:
    """Удаляет карточку"""
    _request("DELETE", f"/cards/{card_id}")
