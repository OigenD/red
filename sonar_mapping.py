#!/usr/bin/python3.8
"""
Скрипт для синхронизации и управления SonarQube с GitLab.

Этапы:
1. Синхронизация групп из GitLab в SonarQube.
2. Обновление списка разрешенных групп для авторизации через GitLab.
3. Назначение прав группам на проекты в SonarQube.
4. Перевод проектов в приватный режим и добавление права на создание проектов.
5. Удаление всех прав у группы sonar-users для каждого проекта.
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
        response = requests.get(url, headers=headers, params=params, timeout=10)
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

    # Получаем группы из GitLab
    print("Получение групп из GitLab...")
    all_groups = []
    page = 1
    while True:
        groups = make_gitlab_request("/api/v4/groups", params={"page": page, "per_page": 100})
        if not groups:
            break
        # Фильтруем группы без родительской группы
        new_groups = [group["name"] for group in groups if group.get("parent_id") is None]
        all_groups.extend(new_groups)
        page += 1

    if not all_groups:
        print("Нет групп в GitLab, удовлетворяющих условию (parent_id == null).")
        sys.exit(1)
    print(f"Получено {len(all_groups)} групп из GitLab: {all_groups}")

    # Синхронизация с SonarQube
    for group_name in all_groups:
        if group_name == ADMIN_GROUP:
            print(f"Группа '{group_name}' пропущена (исключение).")
            continue

        print(f"Обработка группы: {group_name}")
        # Проверяем, существует ли группа в SonarQube
        response = make_sonarqube_request("GET", f"/api/user_groups/search?q={group_name}")
        if response.status_code != 200:
            print(f"Не удалось проверить группу '{group_name}' в SonarQube: Код ответа {response.status_code}")
            sys.exit(1)

        data = parse_json_response(response)
        if data is None:
            sys.exit(1)

        exists = any(group['name'] == group_name for group in data.get('groups', []))
        if exists:
            print(f"Группа '{group_name}' уже существует в SonarQube.")
            continue

        # Создаем группу в SonarQube
        print(f"Группа '{group_name}' не найдена в SonarQube. Создаем...")
        payload = {
            "name": group_name,
            "description": "Group imported from GitLab"
        }
        response = make_sonarqube_request("POST", "/api/user_groups/create", data=payload)
        if response.status_code != 200:
            print(f"Не удалось создать группу '{group_name}' в SonarQube: Код ответа {response.status_code}")
            sys.exit(1)
        print(f"Группа '{group_name}' успешно создана в SonarQube.")

    print("=== Этап 1 завершен успешно ===")

# --- Этап 2: Обновление списка разрешенных групп для авторизации через GitLab ---
def update_allowed_groups():
    print("=== Этап 2: Обновление разрешенных групп для авторизации через GitLab ===")

    # Получаем группы из SonarQube
    print("Получение групп из SonarQube...")
    response = make_sonarqube_request("GET", "/api/user_groups/search")
    if response.status_code != 200:
        print(f"Не удалось получить группы из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    groups = [group["name"] for group in data.get("groups", [])]
    if not groups:
        print("Нет групп в SonarQube. Нечего обновлять.")
        return

    print(f"Найдено {len(groups)} групп в SonarQube: {groups}")

    # Обновляем настройку sonar.auth.gitlab.allowedGroups
    print("Обновление настройки sonar.auth.gitlab.allowedGroups...")
    data = [("key", "sonar.auth.gitlab.allowedGroups")]
    for group in groups:
        data.append(("values", group))

    response = make_sonarqube_request("POST", "/api/settings/set", data=data)
    if response.status_code != 204:
        print(f"Не удалось обновить настройку sonar.auth.gitlab.allowedGroups: Код ответа {response.status_code}")
        sys.exit(1)

    print("Настройка sonar.auth.gitlab.allowedGroups успешно обновлена.")
    print("=== Этап 2 завершен успешно ===")

# --- Этап 3: Назначение прав группам на проекты в SonarQube ---
def assign_project_permissions():
    print("=== Этап 3: Назначение прав группам на проекты в SonarQube ===")

    # Получаем группы из SonarQube
    print("Получение групп из SonarQube...")
    response = make_sonarqube_request("GET", "/api/user_groups/search")
    if response.status_code != 200:
        print(f"Не удалось получить группы из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    groups = [group["name"] for group in data.get("groups", [])]
    print(f"Получено {len(groups)} групп: {groups}")

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

    # Назначаем права
    permissions = ["user", "codeviewer", "issueadmin", "scan", "admin"]
    for project in projects:
        project_key = project["key"]
        project_parts = project_key.split(":")
        if not project_parts:
            print(f"Некорректный ключ проекта: {project_key}")
            continue

        project_group_prefix = project_parts[0]
        for group in groups:
            if project_group_prefix == group:
                print(f"Обнаружено соответствие: группа '{group}' → проект '{project_key}'")
                for permission in permissions:
                    payload = {
                        "groupName": group,
                        "projectKey": project_key,
                        "permission": permission
                    }
                    response = make_sonarqube_request("POST", "/api/permissions/add_group", data=payload)
                    if response.status_code != 204:
                        print(f"Не удалось назначить право '{permission}' для {group}/{project_key}: Код ответа {response.status_code}")
                        sys.exit(1)
                    print(f"Право '{permission}' назначено группе '{group}' для проекта '{project_key}'.")

    print("=== Этап 3 завершен успешно ===")

# --- Этап 4: Перевод проектов в приватный режим и добавление права на создание проектов ---
def privatize_projects_and_grant_provisioning():
    print("=== Этап 4: Приватизация проектов и добавление права на создание ===")

    # Получаем проекты из SonarQube
    print("Получение проектов из SonarQube...")
    response = make_sonarqube_request("GET", "/api/projects/search?ps=500")
    if response.status_code != 200:
        print(f"Не удалось получить проекты из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    projects = [component["key"] for component in data.get("components", [])]
    print(f"Получено {len(projects)} проектов.")

    # Переводим проекты в приватный режим
    if projects:
        print("Перевод проектов в приватный режим...")
        for project in projects:
            payload = {"visibility": "private", "project": project}
            response = make_sonarqube_request("POST", "/api/projects/update_visibility", data=payload)
            if response.status_code != 204:
                print(f"Не удалось перевести проект '{project}' в приватный режим: Код ответа {response.status_code}")
                sys.exit(1)
            print(f"Проект '{project}' переведен в приватный режим.")
    else:
        print("Нет проектов в SonarQube.")

    # Получаем группы из SonarQube
    print("Получение групп из SonarQube...")
    response = make_sonarqube_request("GET", "/api/user_groups/search")
    if response.status_code != 200:
        print(f"Не удалось получить группы из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    groups = [group["name"] for group in data.get("groups", [])]
    print(f"Получено {len(groups)} групп.")

    # Назначаем право provisioning
    if groups:
        print("Назначение права 'provisioning' группам...")
        for group in groups:
            if group == ADMIN_GROUP:
                print(f"Группа '{group}' пропущена (исключение).")
                continue

            # Проверяем, есть ли уже право
            response = make_sonarqube_request("GET", f"/api/permissions/groups?groupName={group}")
            if response.status_code != 200:
                print(f"Не удалось проверить права группы '{group}': Код ответа {response.status_code}")
                sys.exit(1)

            data = parse_json_response(response)
            if data is None:
                sys.exit(1)

            permissions = [perm["permission"] for perm in data.get("permissions", [])]
            if "provisioning" in permissions:
                print(f"Группа '{group}' уже имеет право 'provisioning'.")
                continue

            # Назначаем право
            payload = {"permission": "provisioning", "groupName": group}
            response = make_sonarqube_request("POST", "/api/permissions/add_group", data=payload)
            if response.status_code != 204:
                print(f"Не удалось назначить право 'provisioning' группе '{group}': Код ответа {response.status_code}")
                sys.exit(1)
            print(f"Право 'provisioning' назначено группе '{group}'.")
    else:
        print("Нет групп в SonarQube.")

    print("=== Этап 4 завершен успешно ===")

# --- Этап 5: Удаление всех прав у группы sonar-users для каждого проекта ---
def remove_permissions_from_sonar_users():
    print("=== Этап 5: Удаление прав у группы sonar-users для всех проектов ===")

    # Получаем проекты из SonarQube
    print("Получение проектов из SonarQube...")
    response = make_sonarqube_request("GET", "/api/projects/search?ps=500")
    if response.status_code != 200:
        print(f"Не удалось получить проекты из SonarQube: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    projects = [component["key"] for component in data.get("components", [])]
    print(f"Получено {len(projects)} проектов.")

    if not projects:
        print("Нет проектов в SonarQube.")
        print("=== Этап 5 завершен успешно ===")
        return

    # Проверяем, существует ли группа sonar-users
    print("Проверка существования группы sonar-users...")
    response = make_sonarqube_request("GET", "/api/user_groups/search?q=sonar-users")
    if response.status_code != 200:
        print(f"Не удалось проверить группу sonar-users: Код ответа {response.status_code}")
        sys.exit(1)

    data = parse_json_response(response)
    if data is None:
        sys.exit(1)

    exists = any(group['name'] == "sonar-users" for group in data.get('groups', []))
    if not exists:
        print("Группа sonar-users не найдена в SonarQube. Нечего удалять.")
        print("=== Этап 5 завершен успешно ===")
        return

    # Возможные права, которые могут быть у группы
    possible_permissions = ["user", "codeviewer", "issueadmin", "securityhotspotadmin", "admin", "scan"]

    # Удаляем права у группы sonar-users для каждого проекта
    for project in projects:
        print(f"Обработка проекта: {project}")
        # Проверяем текущие права группы sonar-users для проекта
        response = make_sonarqube_request("GET", f"/api/permissions/groups?groupName=sonar-users&projectKey={project}")
        if response.status_code != 200:
            print(f"Не удалось проверить права группы sonar-users для проекта {project}: Код ответа {response.status_code}")
            sys.exit(1)

        data = parse_json_response(response)
        if data is None:
            sys.exit(1)

        # Логируем полный ответ API для отладки
        print(f"Полный ответ API для проверки прав sonar-users в проекте {project}: {data}")

        # Проверяем, есть ли права в ответе
        current_permissions = []
        if "groups" in data and data["groups"]:
            for group in data["groups"]:
                if group["name"] == "sonar-users" and "permissions" in group:
                    current_permissions = group["permissions"]
                    break

        if current_permissions:
            print(f"Найдены права для группы sonar-users в проекте {project}: {current_permissions}")
        else:
            print(f"Права для группы sonar-users в проекте {project} не найдены в ответе API. Пытаемся удалить все возможные права.")

        # Если права не найдены, всё равно пытаемся удалить все возможные права, чтобы перекрыть унаследованные
        permissions_to_remove = list(set(current_permissions + possible_permissions))

        # Удаляем каждое право
        for permission in permissions_to_remove:
            payload = {
                "groupName": "sonar-users",
                "projectKey": project,
                "permission": permission
            }
            response = make_sonarqube_request("POST", "/api/permissions/remove_group", data=payload)
            if response.status_code != 204:
                print(f"Не удалось удалить право '{permission}' у группы sonar-users для проекта {project}: Код ответа {response.status_code}")
                # Игнорируем ошибку, если право не существует, продолжаем
                continue
            print(f"Право '{permission}' удалено у группы sonar-users для проекта {project}.")

    print("=== Этап 5 завершен успешно ===")

# --- Главная функция ---
def main():
    print("=== Начало выполнения скрипта ===")
    stages = [
        ("Этап 1: Синхронизация групп", sync_groups),
        ("Этап 2: Обновление разрешенных групп", update_allowed_groups),
        ("Этап 3: Назначение прав на проекты", assign_project_permissions),
        ("Этап 4: Приватизация и права на создание", privatize_projects_and_grant_provisioning),
        ("Этап 5: Удаление прав у группы sonar-users", remove_permissions_from_sonar_users)
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
