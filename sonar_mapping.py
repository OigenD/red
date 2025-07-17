```python
import subprocess
import os

def run_command(command, output_file=None):
    try:
        if output_file:
            with open(output_file, 'w') as f:
                subprocess.run(command, shell=True, check=True, stdout=f, universal_newlines=True)
            print(f"Successfully executed: {command} > {output_file}")
        else:
            subprocess.run(command, shell=True, check=True)
            print(f"Successfully executed: {command}")
    except subprocess.CalledProcessError as e:
        print(f"Error executing {command}: {e}")
        raise

def main():
    # Set working directory
    work_dir = "/home/FC/cluster"
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    # Get GitLab token from environment variable
    gitlab_token = os.getenv("GITLAB_TOKEN")
    if not gitlab_token:
        raise ValueError("Missing required environment variable: GITLAB_TOKEN")

    # Create tmp directory if it doesn't exist
    os.makedirs("tmp", exist_ok=True)
    
    # List of commands with their respective output files
    commands = [
        ("kubectl get pods -A -o wide", "tmp/pre-experiment-pods.txt"),
        ("kubectl get nodes -o wide", "tmp/experiment-nodes.txt"),
        ("kubectl get svc -A", "tmp/experiment-svc.txt"),
        ("kubectl get all --all-namespaces -o yaml", "tmp/cluster-state-before.yaml"),
        ("kubectl get events --all-namespaces", "tmp/events-before.txt"),
        ("kubectl get applications.argoproj.io -A -o yaml", "tmp/argocd-applications.yaml"),
        ("kubectl get nodes,pods,services,deployments,statefulsets,daemonsets,replicasets,jobs,cronjobs --all-namespaces -o wide", "tmp/cluster-state.txt"),
        ("kubectl get all,configmap,secret,ingress,storageclass,persistentvolume,persistentvolumeclaim,namespace,role,rolebinding,clusterrole,clusterrolebinding,serviceaccount --all-namespaces -o yaml", "tmp/all-manifests.yaml")
    ]
    
    # Execute cluster info collection commands
    for cmd, outfile in commands:
        run_command(cmd, outfile)
    
    # Git operations
    git_repo_url = f"https://oauth2:{gitlab_token}@git"
    git_commands = [
        # Initialize Git repository if it doesn't exist
        "[ -d .git ] || git init --initial-branch=main",
        f"git remote add origin {git_repo_url} || git remote set-url origin {git_repo_url}",
        # Create initial commit if repository is empty
        "git rev-parse HEAD >/dev/null 2>&1 || (git add . && git commit -m 'Initial commit' --allow-empty)",
        # Stash any unstaged changes
        "git stash push -m 'Auto-stash before pull' || true",
        "git pull --rebase origin main || true",
        # Apply stashed changes
        "git stash pop || true",
        "git add tmp/*",
        f'git commit -m "Обновлено состояние кластера" || true',
        "git push -u origin main"
    ]
    
    # Execute Git commands
    for cmd in git_commands:
        run_command(cmd)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Script failed: {e}")
        exit(1)
```

backapp.sh

#!/bin/bash

# Настройка etcdctl
export ETCDCTL_API=3
export ETCDCTL_ENDPOINTS=https://:2379
export ETCDCTL_CACERT=/etc/ssl/etcd/ssl/ca.pem
export ETCDCTL_CERT=/etc/ssl/etcd/ssl/admin-msk-as1-k8sm-p.fc.ural.ru.pem
export ETCDCTL_KEY=/etc/ssl/etcd/ssl/admin-msk-as1-k8sm-p.fc.ural.ru-key.pem

# Параметры для MinIO
MINIO_ALIAS="myminio"
BUCKET="etcd-backups"
SNAPSHOT_PATH="/tmp/etcd-snapshot.db"
OBJECT_NAME="snapshots/etcd-snapshot-$(date +%Y-%m-%d-%H-%M-%S).db"

# Проверка и создание бакета
mc mb $MINIO_ALIAS/$BUCKET 2>/dev/null || true

# Создание снапшота
etcdctl snapshot save $SNAPSHOT_PATH

# Проверка успешности создания снапшота
if [ $? -eq 0 ]; then
  echo "Snapshot created successfully: $SNAPSHOT_PATH"
else
  echo "Failed to create snapshot"
  exit 1
fi

# Загрузка в MinIO
mc cp $SNAPSHOT_PATH $MINIO_ALIAS/$BUCKET/$OBJECT_NAME

# Проверка успешности загрузки
if [ $? -eq 0 ]; then
  echo "Snapshot uploaded to $MINIO_ALIAS/$BUCKET/$OBJECT_NAME"
  # Удаление локального файла
  rm $SNAPSHOT_PATH
else
  echo "Failed to upload snapshot to MinIO"
  exit 1
fi
