#!/usr/bin/python3.8
"""
Скрипт для выполнения команды kubectl, сохранения результата в backapp.yaml
и отправки файла в GitLab репозиторий через API.

Этапы:
1. Выполнение команды /usr/local/bin/kubectl get applications -A -o yaml.
2. Сохранение результата в backapp.yaml.
3. Отправка файла в GitLab по пути playbooks/argocd/backapp.yaml.
"""

import os
import sys
import subprocess
import requests
import base64
import json
from typing import Dict, Any

# --- Конфигурация ---
GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.fc.uralsibbank.ru").rstrip('/')
GITLAB_TOKEN = os.environ.get("gitlab_token")
REPO_PATH = "sre-platfom-support/ansible-00000"
FILE_PATH = "playbooks/argocd/backapp.yaml"
BRANCH = "main"
KUBECTL_COMMAND = "/usr/local/bin/kubectl get applications -A -o yaml"
OUTPUT_FILE = "backapp.yaml"

# Проверка переменных окружения
if not GITLAB_TOKEN:
    print("Ошибка: Переменная окружения 'gitlab_token' не установлена.")
    sys.exit(1)

# Удаляем лишние пробелы из токена
GITLAB_TOKEN = GITLAB_TOKEN.strip()

# --- Вспомогательные функции ---
def make_gitlab_request(method: str, endpoint: str, data: Dict[str, Any] = None) -> Any:
    """Выполняет запрос к GitLab API."""
    url = f"{GITLAB_URL}{endpoint}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN, "Content-Type": "application/json"}
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            verify=False,
            timeout=10
        )
        print(f"GitLab API: {method} {url} -> Код ответа: {response.status_code}")
        print(f"GitLab API: Ответ: {response.text}")
        response.raise_for_status()
        return response.json() if response.text else None
    except requests.RequestException as e:
        print(f"Ошибка при запросе к GitLab API ({url}): {e}")
        sys.exit(1)

def run_kubectl_command():
    """Выполняет команду kubectl и сохраняет результат в файл."""
    print(f"Выполнение команды: {KUBECTL_COMMAND}")
    try:
        with open(OUTPUT_FILE, "w") as f:
            result = subprocess.run(
                KUBECTL_COMMAND,
                shell=True,
                check=True,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True
            )
        print(f"Команда выполнена успешно. Результат сохранен в {OUTPUT_FILE}.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды kubectl: {e.stderr}")
        sys.exit(1)
    except IOError as e:
        print(f"Ошибка при записи в файл {OUTPUT_FILE}: {e}")
        sys.exit(1)

def read_file_content():
    """Читает содержимое файла backapp.yaml."""
    print(f"Чтение файла {OUTPUT_FILE}...")
    try:
        with open(OUTPUT_FILE, "r") as f:
            content = f.read()
        if not content:
            print(f"Ошибка: Файл {OUTPUT_FILE} пуст.")
            sys.exit(1)
        print(f"Файл {OUTPUT_FILE} успешно прочитан.")
        return content
    except IOError as e:
        print(f"Ошибка при чтении файла {OUTPUT_FILE}: {e}")
        sys.exit(1)

def encode_file_content(content: str) -> str:
    """Кодирует содержимое файла в base64."""
    return base64.b64encode(content.encode("utf-8")).decode("utf-8")

def update_gitlab_file():
    """Обновляет файл в GitLab через API."""
    print(f"Отправка файла {OUTPUT_FILE} в GitLab ({FILE_PATH})...")

    # Получаем информацию о файле из репозитория
    encoded_file_path = requests.utils.quote(FILE_PATH)
    endpoint = f"/api/v4/projects/{requests.utils.quote(REPO_PATH)}/repository/files/{encoded_file_path}"
    file_info = make_gitlab_request("GET", f"{endpoint}?ref={BRANCH}")

    # Читаем содержимое локального файла
    content = read_file_content()
    encoded_content = encode_file_content(content)

    # Формируем данные для обновления файла
    data = {
        "branch": BRANCH,
        "content": encoded_content,
        "commit_message": f"Update {FILE_PATH} with latest kubectl output",
        "encoding": "base64"
    }

    # Если файл существует, обновляем его
    if file_info:
        print(f"Файл {FILE_PATH} существует в репозитории. Обновляем...")
        response = make_gitlab_request("PUT", endpoint, data=data)
    else:
        print(f"Файл {FILE_PATH} не найден в репозитории. Создаем...")
        response = make_gitlab_request("POST", f"{endpoint}", data=data)

    print(f"Файл {FILE_PATH} успешно обновлен в GitLab.")
    return response

# --- Главная функция ---
def main():
    print("=== Начало выполнения скрипта ===")
    try:
        # Этап 1: Выполнение команды kubectl
        print("Этап 1: Выполнение команды kubectl и сохранение результата")
        run_kubectl_command()

        # Этап 2: Обновление файла в GitLab
        print("Этап 2: Обновление файла в GitLab")
        update_gitlab_file()

    except Exception as e:
        print(f"Ошибка выполнения скрипта: {e}")
        sys.exit(1)

    print("=== Скрипт выполнен успешно ===")

if __name__ == "__main__":
    main()
