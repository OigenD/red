#!/usr/bin/python3.8
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
    work_dir = "/home/FC/dikev/cluster"
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    # Get GitLab token from environment variable
    gitlab_token = os.getenv("GITLAB_TOKEN")
    if not gitlab_token:
        raise ValueError("Missing required environment variable: GITLAB_TOKEN")

    # Create tmp directory if it doesn't exist
    os.makedirs("tmp", exist_ok=True)
    
    # List of commands with their respective output files
    base_commands = [
        ("kubectl get pods -A -o wide", "tmp/pre-experiment-pods.txt"),
        ("kubectl get nodes -o wide", "tmp/experiment-nodes.txt"),
        ("kubectl get svc -A", "tmp/experiment-svc.txt"),
        ("kubectl get all --all-namespaces -o yaml", "tmp/cluster-state-before.yaml"),
        ("kubectl get events --all-namespaces", "tmp/events-before.txt"),
        ("kubectl get applications.argoproj.io -A -o yaml", "tmp/argocd-applications.yaml"),
        ("kubectl get nodes,pods,services,deployments,statefulsets,daemonsets,replicasets,jobs,cronjobs --all-namespaces -o wide", "tmp/cluster-state.txt"),
        ("kubectl get all,configmap,secret,ingress,storageclass,persistentvolume,persistentvolumeclaim,namespace,role,rolebinding,clusterrole,clusterrolebinding,serviceaccount,services,deployments,statefulsets,daemonsets,replicasets,jobs,cronjobs --all-namespaces -o yaml", "tmp/all-manifests.yaml")
    ]
    
    additional_commands = [
        # Автомасштабирование
        ("kubectl get horizontalpodautoscalers.autoscaling -A -o yaml", "tmp/hpa.yaml"),
        ("kubectl get verticalpodautoscalers.autoscaling.k8s.io -A -o yaml", "tmp/vpa.yaml"),
        
        # Сеть
        ("kubectl get networkpolicies.networking.k8s.io -A -o yaml", "tmp/networkpolicies.yaml"),
        ("kubectl get endpointslices.discovery.k8s.io -A -o yaml", "tmp/endpointslices.yaml"),
        
        # Бюджеты и квоты
        ("kubectl get poddisruptionbudgets.policy -A -o yaml", "tmp/pdb.yaml"),
        ("kubectl get resourcequotas -A -o yaml", "tmp/resourcequotas.yaml"),
        ("kubectl get limitranges -A -o yaml", "tmp/limitranges.yaml"),
        
        # Адмиссия и хуки
        ("kubectl get mutatingwebhookconfigurations.admissionregistration.k8s.io -o yaml", "tmp/mutatingwebhooks.yaml"),
        ("kubectl get validatingwebhookconfigurations.admissionregistration.k8s.io -o yaml", "tmp/validatingwebhooks.yaml"),
        
        # API и расширения
        ("kubectl get crds.apiextensions.k8s.io -o yaml", "tmp/crds.yaml"),
        ("kubectl get apiservices.apiregistration.k8s.io -o yaml", "tmp/apiservices.yaml"),
        ("kubectl get priorityclasses.scheduling.k8s.io -o yaml", "tmp/priorityclasses.yaml"),
        
        # Другие системные
        ("kubectl get leases.coordination.k8s.io -A -o yaml", "tmp/leases.yaml"),
        ("kubectl get certificates.certificates.k8s.io -A -o yaml", "tmp/certificates.yaml"),
        ("kubectl get runtimeclasses.node.k8s.io -o yaml", "tmp/runtimeclasses.yaml")
    ]
    
    # Динамический сбор всех namespaced и cluster-scoped ресурсов
    dynamic_namespaced_cmd = "kubectl api-resources --verbs=list --namespaced=true -o name | xargs -n 1 kubectl get --ignore-not-found -A -o yaml"
    dynamic_cluster_cmd = "kubectl api-resources --verbs=list --namespaced=false -o name | xargs -n 1 kubectl get --ignore-not-found -o yaml"
    
    # Объединяем все команды
    commands = base_commands + additional_commands + [
        (dynamic_namespaced_cmd, "tmp/full-namespaced.yaml"),
        (dynamic_cluster_cmd, "tmp/full-cluster.yaml")
    ]
    
    # Execute cluster info collection commands
    for cmd, outfile in commands:
        run_command(cmd, outfile)
    
    # Дополнительно: Собираем все CR instances динамически (после CRD)
    # Это опционально, но для полноты: парсим CRD и get instances
    try:
        with open("tmp/crds.yaml", 'r') as f:
            crds_data = yaml.safe_load_all(f)
            for crd in crds_data:
                if crd and crd.get('kind') == 'CustomResourceDefinition':
                    name = crd['metadata']['name']
                    plural = name.rsplit('.', 1)[0]
                    group = name.rsplit('.', 1)[1]
                    instance_cmd = f"kubectl get {plural}.{group} -A -o yaml"
                    output_file = f"tmp/{plural}-{group}.yaml"
                    run_command(instance_cmd, output_file)
                    print(f"Collected instances for CRD: {name}")
    except Exception as e:
        print(f"Warning: Could not collect CR instances dynamically: {e}")
    
    # Git operations
    git_repo_url = f"https://oauth2:{gitlab_token}@gitlab."
    git_commands = [
        # Initialize Git repository if it doesn't exist
        "[ -d .git ] || git init --initial-branch=main",
        f"git remote add origin {git_repo_url} || git remote set-url origin {git_repo_url}",
        "git config user.name ''",
        "git config user.email ''",
        # Create initial commit if repository is empty
        "git rev-parse HEAD >/dev/null 2>&1 || (git add . && git commit -m 'Initial commit' --allow-empty)",
        # Stash any unstaged changes
        "git stash push -m 'Auto-stash before pull' || true",
        "git pull --rebase origin main || true",
        # Apply stashed changes
        "git stash pop || true",
        "git add tmp/*",
        f'git commit -m "Обновлено состояние кластера (полный дамп)" || true',
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
