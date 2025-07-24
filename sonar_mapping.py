#!/usr/bin/env python3

import os
import subprocess
import datetime

# Параметры для etcdctl
ENDPOINTS = "https://10.167.122.52:2379"
CACERT = "/etc/ssl/etcd/ssl/ca.pem"
CERT = "/etc/ssl/etcd/ssl/admin-msk-as1-k8sm-p.fc.uralsibbank.ru.pem"
KEY = "/etc/ssl/etcd/ssl/admin-msk-as1-k8sm-p.fc.uralsibbank.ru-key.pem"

# Параметры для MinIO
MINIO_ALIAS = "minio"
MINIO_ENDPOINT = "http://minio.fc.uralsibbank.ru:9000"
MINIO_ACCESS_KEY = "etcd-backup"
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
BUCKET = "etcd-backups"
SNAPSHOT_PATH = "/tmp/etcd-snapshot.db"
OBJECT_NAME = f"snapshots/etcd-snapshot-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.db"

# Проверка и создание бакета
subprocess.run(["/home/FC/dikev/etcd_back/mc", "alias", "set", MINIO_ALIAS, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY])
subprocess.run(["/home/FC/dikev/etcd_back/mc", "mb", f"{MINIO_ALIAS}/{BUCKET}", "--ignore-existing"])

# Создание снапшота
cmd = [
    "etcdctl",
    "--endpoints", ENDPOINTS,
    "--cacert", CACERT,
    "--cert", CERT,
    "--key", KEY,
    "snapshot", "save", SNAPSHOT_PATH
]
result = subprocess.run(cmd, env={"ETCDCTL_API": "3"}, capture_output=True, text=True)

# Проверка успешности создания снапшота
if result.returncode == 0:
    print(f"Snapshot created successfully: {SNAPSHOT_PATH}")
else:
    print("Failed to create snapshot")
    exit(1)

# Загрузка в MinIO
subprocess.run(["/home/FC/dikev/etcd_back/mc", "cp", SNAPSHOT_PATH, f"{MINIO_ALIAS}/{BUCKET}/{OBJECT_NAME}"])

# Проверка успешности загрузки
if result.returncode == 0:
    print(f"Snapshot uploaded to {MINIO_ALIAS}/{BUCKET}/{OBJECT_NAME}")
    # Удаление локального файла
    os.remove(SNAPSHOT_PATH)
else:
    print("Failed to upload snapshot to MinIO")
    exit(1)
