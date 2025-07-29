#!/usr/bin/env python3
import os
import subprocess
import datetime
import sys

# Параметры для Ceph
CEPH_CONF = "/etc/ceph/ceph.conf"
CEPH_KEYRING = "/etc/ceph/ceph.client.admin.keyring"
ROOK_CEPH_TOOLS_POD = "kubectl get pod -n rook-ceph -l app=rook-ceph-tools -o name"

# Параметры для MinIO
MINIO_ALIAS = "minio"
MINIO_ENDPOINT = "http://minio.fc.uralsibbank.ru:9000"
MINIO_ACCESS_KEY = "etcd-backup"  # Замените на ваши учетные данные
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET = "ceph-backups"

# Пути к бинарникам
MC_PATH = "/usr/local/bin/mc"  # Путь к mc, обновите, если требуется
KUBECTL_PATH = "/usr/bin/kubectl"  # Путь к kubectl
RBD_PATH = "/usr/bin/rbd"  # Путь к rbd в поде rook-ceph-tools

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
    return True

def run_command(cmd, env=None):
    """Выполняет команду с обработкой ошибок"""
    try:
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}", file=sys.stderr)
        return False, "", str(e)

def get_rook_ceph_tools_pod():
    """Получает имя пода rook-ceph-tools"""
    success, stdout, stderr = run_command([KUBECTL_PATH, "get", "pod", "-n", "rook-ceph", "-l", "app=rook-ceph-tools", "-o", "name"])
    if not success:
        print("Ошибка получения имени пода rook-ceph-tools", file=sys.stderr)
        return None
    return stdout.strip()

def get_pools(pod):
    """Получает список всех пулов Ceph"""
    cmd = [
        KUBECTL_PATH, "exec", "-n", "rook-ceph", pod, "--",
        RBD_PATH, "pool", "ls",
        "--conf", CEPH_CONF, "--keyring", CEPH_KEYRING
    ]
    success, stdout, stderr = run_command(cmd)
    if not success:
        print("Ошибка получения списка пулов", file=sys.stderr)
        return []
    return [line.strip() for line in stdout.splitlines() if line.strip()]

def get_images(pod, pool):
    """Получает список всех RBD-образов в пуле"""
    cmd = [
        KUBECTL_PATH, "exec", "-n", "rook-ceph", pod, "--",
        RBD_PATH, "ls", pool,
        "--conf", CEPH_CONF, "--keyring", CEPH_KEYRING
    ]
    success, stdout, stderr = run_command(cmd)
    if not success:
        print(f"Ошибка получения списка образов в пуле {pool}", file=sys.stderr)
        return []
    return [line.strip() for line in stdout.splitlines() if line.strip()]

def get_snapshots(pod, pool, image):
    """Получает список снапшотов для указанного RBD-образа"""
    cmd = [
        KUBECTL_PATH, "exec", "-n", "rook-ceph", pod, "--",
        RBD_PATH, "snap", "ls", f"{pool}/{image}",
        "--conf", CEPH_CONF, "--keyring", CEPH_KEYRING
    ]
    success, stdout, stderr = run_command(cmd)
    if not success:
        print(f"Ошибка получения списка снапшотов для {pool}/{image}", file=sys.stderr)
        return []
    
    snapshots = []
    lines = stdout.splitlines()
    for line in lines[1:]:  # Пропускаем заголовок
        parts = line.split()
        if parts and len(parts) > 1:
            snapshots.append(parts[1])  # Имя снапшота во втором столбце
    return snapshots

def export_snapshot(pod, pool, image, snapshot):
    """Экспортирует снапшот в файл"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    snapshot_path = f"/tmp/ceph-snapshot-{pool}-{image}-{snapshot}-{timestamp}.img"
    object_name = f"snapshots/{pool}/{image}/ceph-snapshot-{snapshot}-{timestamp}.img"

    cmd = [
        KUBECTL_PATH, "exec", "-n", "rook-ceph", pod, "--",
        RBD_PATH, "export",
        f"{pool}/{image}@{snapshot}",
        snapshot_path,
        "--conf", CEPH_CONF, "--keyring", CEPH_KEYRING
    ]

    success, _, _ = run_command(cmd)
    if not success:
        print(f"Ошибка экспорта снапшота {snapshot} для {pool}/{image}", file=sys.stderr)
        return None, None
    return snapshot_path, object_name

def main():
    if not check_binaries():
        return 1

    # Устанавливаем алиас MinIO
    if not run_command([MC_PATH, "alias", "set", MINIO_ALIAS, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY])[0]:
        return 1

    # Проверяем доступ к бакету
    if not run_command([MC_PATH, "ls", f"{MINIO_ALIAS}/{BUCKET}"])[0]:
        print(f"Ошибка доступа к бакету {BUCKET}", file=sys.stderr)
        return 1

    # Получаем имя пода rook-ceph-tools
    pod = get_rook_ceph_tools_pod()
    if not pod:
        return 1

    # Получаем список всех пулов
    pools = get_pools(pod)
    if not pools:
        print("Пулы не найдены", file=sys.stderr)
        return 1

    print(f"Найдено пулов: {len(pools)} ({', '.join(pools)})")

    # Перебираем пулы, образы и снапшоты
    for pool in pools:
        images = get_images(pod, pool)
        if not images:
            print(f"Образы в пуле {pool} не найдены", file=sys.stderr)
            continue

        print(f"Найдено образов в пуле {pool}: {len(images)} ({', '.join(images)})")

        for image in images:
            snapshots = get_snapshots(pod, pool, image)
            if not snapshots:
                print(f"Снапшоты для {pool}/{image} не найдены", file=sys.stderr)
                continue

            print(f"Найдено снапшотов для {pool}/{image}: {len(snapshots)} ({', '.join(snapshots)})")

            # Экспортируем и загружаем каждый снапшот
            for snapshot in snapshots:
                snapshot_path, object_name = export_snapshot(pod, pool, image, snapshot)
                if not snapshot_path:
                    continue

                # Загружаем в MinIO
                if not run_command([MC_PATH, "cp", snapshot_path, f"{MINIO_ALIAS}/{BUCKET}/{object_name}"])[0]:
                    print(f"Ошибка загрузки снапшота {snapshot} для {pool}/{image} в MinIO", file=sys.stderr)
                    continue

                print(f"Снапшот {snapshot} для {pool}/{image} загружен в {MINIO_ALIAS}/{BUCKET}/{object_name}")

                # Удаляем временный файл
                try:
                    os.remove(snapshot_path)
                except OSError as e:
                    print(f"Предупреждение: не удалось удалить временный файл {snapshot_path}: {e}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    sys.exit(main())
