import json
import os
import logging
import base64
import urllib.request
import urllib.parse

from bot.config import TICKTICK_CLIENT_ID, TICKTICK_CLIENT_SECRET

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ticktick.com/open/v1"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
REDIRECT_URI = "https://localhost"

# Токен хранится в памяти (+ env переменная для переживания деплоя)
_access_token: str = os.getenv("TICKTICK_ACCESS_TOKEN", "")


def get_auth_url() -> str:
    """Генерирует URL для авторизации пользователя"""
    params = {
        "client_id": TICKTICK_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "tasks:read tasks:write",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Обменивает код авторизации на токен"""
    # TickTick требует Basic Auth с client_id:client_secret
    credentials = base64.b64encode(
        f"{TICKTICK_CLIENT_ID}:{TICKTICK_CLIENT_SECRET}".encode()
    ).decode()

    data = urllib.parse.urlencode({
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Authorization", f"Basic {credentials}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))

    # Сохраняем токен в память
    global _access_token
    _access_token = token_data.get("access_token", "")

    logger.info(f"TickTick токен получен. Добавь в Railway Variables: TICKTICK_ACCESS_TOKEN={_access_token}")
    return token_data


def _get_token() -> str:
    """Получает access_token"""
    return _access_token


def is_connected() -> bool:
    """Проверяет подключён ли TickTick"""
    return bool(_get_token())


def _request(method: str, path: str, body: dict = None) -> dict:
    """Запрос к TickTick API"""
    token = _get_token()
    if not token:
        raise Exception("TickTick не авторизован. Используй /ticktick для подключения.")

    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_projects() -> list[dict]:
    """Получает все проекты (списки задач)"""
    return _request("GET", "/project")


def get_tasks(project_id: str) -> list[dict]:
    """Получает задачи проекта"""
    data = _request("GET", f"/project/{project_id}/data")
    return data.get("tasks", [])


def get_all_tasks() -> list[dict]:
    """Получает все задачи из всех проектов"""
    all_tasks = []
    projects = get_projects()
    for project in projects:
        tasks = get_tasks(project["id"])
        for task in tasks:
            task["_project_name"] = project.get("name", "")
        all_tasks.extend(tasks)
    return all_tasks


def _get_inbox_project_id() -> str:
    """Получает ID проекта Inbox (первый проект по умолчанию)"""
    projects = get_projects()
    # Ищем inbox
    for p in projects:
        if p.get("kind") == "INBOX" or p.get("name", "").lower() == "inbox":
            return p["id"]
    # Если не нашли — берём первый
    if projects:
        return projects[0]["id"]
    return ""


def create_task(title: str, content: str = "", project_id: str = None, due_date: str = None) -> dict:
    """
    Создаёт задачу в TickTick.
    due_date: формат "2026-04-20T08:00:00+0000"
    """
    # Если проект не указан — создаём в Inbox
    if not project_id:
        project_id = _get_inbox_project_id()

    body = {
        "title": title,
        "projectId": project_id,
    }
    if content:
        body["content"] = content
    if due_date:
        body["dueDate"] = due_date

    result = _request("POST", "/task", body)
    logger.info(f"TickTick задача создана: {title} (project: {project_id}, id: {result.get('id', '?')})")
    return result


def complete_task(task_id: str, project_id: str) -> dict:
    """Отмечает задачу выполненной"""
    return _request("POST", f"/project/{project_id}/task/{task_id}/complete")
