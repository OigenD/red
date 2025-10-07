#!/usr/bin/env python3
import os
import subprocess
import datetime
import sys

# Timestamp для файлов
timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

# Параметры для MinIO
MINIO_ALIAS = "minio"
MINIO_ENDPOINT = "http://minio.fc.uralsibbank.ru:9000"
MINIO_ACCESS_KEY = "etcd-backup"  # Можно изменить на db-backup, если нужно
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET = "db-backups"  # Новый бакет для дампов БД, создайте его заранее
DUMP_PATH = f"/tmp/pg-dump-{timestamp}.sql"
OBJECT_NAME = f"snapshots/pg-dump-{timestamp}.sql"

# Параметры для K8s и PostgreSQL (на основе предоставленной конфигурации)
NAMESPACE = "sonarqube"
POD_NAME = "postgresql-0"  # Стандартное имя пода для bitnami/postgresql StatefulSet
PG_USER = "sonar"
PG_DB = "sonar"
PG_PASSWORD = os.getenv("PG_PASSWORD")  # Пароль из env (получите из Vault перед запуском)

# Пути к бинарникам
MC_PATH = "/home/FC/dikev/etcd_back/mc"
KUBECTL_PATH = "/usr/bin/kubectl"  # Стандартный путь для kubectl

def check_binaries():
    """Проверяет наличие необходимых бинарных файлов"""
    required_bins = {
        'mc': MC_PATH,
        'kubectl': KUBECTL_PATH
    }

    missing = []
    for name, path in required_bins.items():
        if not os.path.exists(path):
            missing.append(f"{name} ({path})")

    if missing:
        print(f"Ошибка: Не найдены необходимые компоненты: {', '.join(missing)}")
        print("Проверьте пути в скрипте или установите отсутствующие компоненты")
        return False

    # Проверяем обязательные env vars
    missing_env = []
    if not PG_PASSWORD:
        missing_env.append("PG_PASSWORD")

    if missing_env:
        print(f"Ошибка: Отсутствуют обязательные переменные окружения: {', '.join(missing_env)}")
        print("Установите их перед запуском: export PG_PASSWORD=... (получите из Vault)")
        return False

    # Проверяем, что под существует
    check_pod_cmd = [KUBECTL_PATH, "get", "pod", POD_NAME, "-n", NAMESPACE, "--no-headers"]
    try:
        subprocess.run(check_pod_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except subprocess.CalledProcessError:
        print(f"Ошибка: Под {POD_NAME} в namespace {NAMESPACE} не найден. Проверьте имя пода.")
        return False

    return True

def run_command(cmd, output_file=None, shell=False):
    """Выполняет команду с обработкой ошибок и опциональным выводом в файл"""
    try:
        if output_file:
            with open(output_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    shell=shell,
                    check=True,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
            print(f"Успешно выполнено: {' '.join(cmd if isinstance(cmd, list) else cmd)} > {output_file}")
        else:
            result = subprocess.run(
                cmd,
                shell=shell,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            print(f"Успешно выполнено: {' '.join(cmd if isinstance(cmd, list) else cmd)}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения команды {' '.join(cmd if isinstance(cmd, list) else cmd)}: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return False
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        return False

def main():
    if not check_binaries():
        return 1

    # Устанавливаем алиас MinIO
    if not run_command([
        MC_PATH, "alias", "set",
        MINIO_ALIAS, MINIO_ENDPOINT,
        MINIO_ACCESS_KEY, MINIO_SECRET_KEY
    ]):
        return 1

    # Проверяем доступ к бакету (создайте бакет заранее, если его нет)
    if not run_command([MC_PATH, "ls", f"{MINIO_ALIAS}/{BUCKET}"]):
        print(f"Ошибка доступа к бакету {BUCKET}. Создайте его в MinIO, если не существует.", file=sys.stderr)
        return 1

    # Создаем дамп PostgreSQL через kubectl exec
    # Передаем PGPASSWORD как env var для pg_dump
    pg_dump_cmd = [
        KUBECTL_PATH, "exec", "-n", NAMESPACE, POD_NAME, "--env", f"PGPASSWORD={PG_PASSWORD}",
        "--", "pg_dump",
        "-U", PG_USER,
        "-d", PG_DB,
        "-h", "localhost",
        "-p", "5432",
        "--no-owner",
        "--no-privileges",
        "--verbose"
    ]

    if not run_command(pg_dump_cmd, output_file=DUMP_PATH):
        print("Ошибка создания дампа PostgreSQL", file=sys.stderr)
        return 1

    print(f"Дамп успешно создан: {DUMP_PATH}")

    # Загружаем в MinIO
    if not run_command([
        MC_PATH, "cp",
        DUMP_PATH,
        f"{MINIO_ALIAS}/{BUCKET}/{OBJECT_NAME}"
    ]):
        print("Ошибка загрузки дампа в MinIO", file=sys.stderr)
        return 1

    print(f"Дамп загружен в {MINIO_ALIAS}/{BUCKET}/{OBJECT_NAME}")

    # Удаляем временный файл
    try:
        os.remove(DUMP_PATH)
        print(f"Временный файл удален: {DUMP_PATH}")
    except OSError as e:
        print(f"Предупреждение: не удалось удалить временный файл: {e}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    sys.exit(main())
