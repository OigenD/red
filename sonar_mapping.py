#!/usr/bin/python3.8
"""
Скрипт для синхронизации и управления SonarQube с GitLab.

Этапы:
1. Синхронизация групп из GitLab в SonarQube.
2. Обновление списка разрешенных групп для авторизации через GitLab.
3. Назначение прав группам на проекты в SonarQube.
4. Перевод проектов в приватный режим и добавление права на создание проектов.
5. Удаление всех прав у группы sonar-users для каждого проекта.
6. Назначение прав группе ib_audit на все проекты.
"""

import os
import sys
import requests
import json
from typing import List, Dict, Any

# --- Конфигурация ---
GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.fc.uralsibbank.ru").rstrip('/')
GITLAB_TOKEN = os.environ.get("gitlab_token")
SONARQUBE_URL = os.environ.get("SONARQUBE_URL", "https://sonarqube.sre.fc.uralsibbank.ru").rstrip('/')
SONARQUBE_TOKEN = os.environ.get("sonarqube_token")
ADMIN_GROUP = "sre-platfom-support"

# Проверка переменных окружения
if not GITLAB_TOKEN:
    print("Ошибка: Переменная окружения 'gitlab_token' не установлена.")
    sys.exit(1)
if not SONARQUBE_TOKEN:
    print("Ошибка: Переменная окружения 'sonarqube_token' не установлена.")
    sys.exit(1)

# Удаляем лишние пробелы из токенов
GITLAB_TOKEN = GITLAB_TOKEN.strip()
SONARQUBE_TOKEN = SONARQUBE_TOKEN.strip()

# Настройка аутентификации для SonarQube (Basic Auth: токен как имя пользователя, пароль пустой)
SONARQUBE_AUTH = (SONARQUBE_TOKEN, "")
SONARQUBE_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# --- Вспомогательные функции ---
def make_gitlab_request(endpoint: str, params: Dict[str, Any] = None) -> Any:
    """Выполняет запрос к GitLab API."""
    url = f"{GITLAB_URL}{endpoint}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    try:
        response = requests.get(url, headers=headers, params=params, verify='/etc/pki/ca-trust/source/anchors/msk-as01gitlab.fc.uralsibbank.ru.crt', timeout=10)
        print(f"GitLab API: Запрос к {url} -> Код ответа: {response.status_code}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при запросе к GitLab API ({url}): {e}")
        print(f"Текст ответа: {response.text if 'response' in locals() else 'нет ответа'}")
        raise

def make_sonarqube_request(method: str, endpoint: str, data: Dict[str, Any] = None) -> requests.Response:
    """Выполняет запрос к SonarQube API."""
    url = f"{SONARQUBE_URL}{endpoint}"
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=SONARQUBE_HEADERS,
            auth=SONARQUBE_AUTH,
            data=data,
            timeout=10
        )
        print(f"SonarQube API: {method} {url} -> Код ответа: {response.status_code}")
        print(f"SonarQube API: Ответ: {response.text}")
        return response
    except requests.RequestException as e:
        print(f"Ошибка при запросе к SonarQube API ({url}): {e}")
        raise

def parse_json_response(response: requests.Response) -> Any:
    """Парсит JSON из ответа SonarQube."""
    if not response.text:
        print("Ошибка: SonarQube вернул пустой ответ.")
        return None
    try:
        return response.json()
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON: {e}")
        print(f"Текст ответа: {response.text}")
        raise

# --- Этап 1: Синхронизация групп из GitLab в SonarQube ---
def sync_groups():
    print("=== Этап 1: Синхронизация групп из GitLab в SonarQube ===")
    # ... (оставляем без изменений)

# --- Этап 2: Обновление списка разрешенных групп для авторизации через GitLab ---
def update_allowed_groups():
    print("=== Этап 2: Обновление разрешенных групп для авторизации через GitLab ===")
    # ... (оставляем без изменений)

# --- Этап 3: Назначение прав группам на проекты в SonarQube ---
def assign_project_permissions():
    print("=== Этап 3: Назначение прав группам на проекты в SonarQube ===")
    # ... (оставляем без изменений)

# --- Этап 4: Перевод проектов в приватный режим и добавление права на создание ---
def privatize_projects_and_grant_provisioning():
    print("=== Этап 4: Приватизация проектов и добавление права на создание ===")
    # ... (оставляем без изменений)

# --- Этап 5: Удаление всех прав у группы sonar-users для каждого проекта ---
def remove_permissions_from_sonar_users():
    print("=== Этап 5: Удаление прав у группы sonar-users для всех проектов ===")
    # ... (оставляем без изменений)

# --- Этап 3.1: Назначение прав группе ib_audit на все проекты ---
def assign_audit_permissions():
    print("=== Этап 3.1: Назначение прав группе ib_audit на все проекты ===")

    # Константа для группы ib_audit
    AUDIT_GROUP = "ib_audit"

    # Получаем проекты из SonarQube
    print("Получение проектов из SonarQube...")
    response = make_sonarqube_request("GET", "/api/projects/search")
    if response.status_code != 200:
        print(f"Не удалось получить проекты из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    projects = data.get("components", [])
    print(f"Получено {len(projects)} проектов.")

    # Права, которые будут назначены группе ib_audit
    audit_permissions = ["user", "codeviewer", "issueadmin", "scan"]

    # Проверяем существование группы ib_audit в SonarQube
    print(f"Проверка существования группы '{AUDIT_GROUP}' в SonarQube...")
    response = make_sonarqube_request("GET", f"/api/user_groups/search?q={AUDIT_GROUP}")
    if response.status_code != 200:
        print(f"Не удалось проверить группу '{AUDIT_GROUP}' в SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    exists = any(group['name'] == AUDIT_GROUP for group in data.get('groups', []))
    if not exists:
        print(f"Группа '{AUDIT_GROUP}' не найдена в SonarQube. Создаем...")
        payload = {
            "name": AUDIT_GROUP,
            "description": "Group for ib_audit (security service)"
        }
        response = make_sonarqube_request("POST", "/api/user_groups/create", data=payload)
        if response.status_code != 200:
            print(f"Не удалось создать группу '{AUDIT_GROUP}' в SonarQube: Код ответа {response.status_code}")
            sys.exit(1)
        print(f"Группа '{AUDIT_GROUP}' успешно создана в SonarQube.")
    else:
        print(f"Группа '{AUDIT_GROUP}' уже существует в SonarQube.")

    # Назначаем права группе ib_audit на все проекты
    for project in projects:
        project_key = project["key"]
        print(f"Назначение прав группе '{AUDIT_GROUP}' для проекта '{project_key}'...")
        for permission in audit_permissions:
            payload = {
                "groupName": AUDIT_GROUP,
                "projectKey": project_key,
                "permission": permission
            }
            response = make_sonarqube_request("POST", "/api/permissions/add_group", data=payload)
            if response.status_code != 204:
                print(f"Не удалось назначить право '{permission}' группе '{AUDIT_GROUP}' для проекта '{project_key}': Код ответа {response.status_code}")
                continue
            print(f"Право '{permission}' назначено группе '{AUDIT_GROUP}' для проекта '{project_key}'.")

    print("=== Этап 3.1 завершен успешно ===")

# --- Главная функция ---
def main():
    print("=== Начало выполнения скрипта ===")
    stages = [
        ("Этап 1: Синхронизация групп", sync_groups),
        ("Этап 2: Обновление разрешенных групп", update_allowed_groups),
        ("Этап 3: Назначение прав на проекты", assign_project_permissions),
        ("Этап 4: Приватизация и права на создание", privatize_projects_and_grant_provisioning),
        ("Этап 5: Удаление прав у группы sonar-users", remove_permissions_from_sonar_users),
        ("Этап 3.1: Назначение прав группе ib_audit", assign_audit_permissions)
    ]

    for stage_name, stage_func in stages:
        print(f"Запуск: {stage_name}")
        try:
            stage_func()
        except Exception as e:
            print(f"Ошибка в {stage_name}: {e}")
            sys.exit(1)
        print(f"{stage_name} завершен.\n")

    print("=== Скрипт выполнен успешно ===")

if __name__ == "__main__":
    main()
