```python
import subprocess
import datetime
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
    # Get ArgoCD and GitLab credentials from environment variables
    argocd_server = os.getenv("ARGOCD_SERVER")
    argocd_username = os.getenv("ARGOCD_USERNAME")
    argocd_password = os.getenv("ARGOCD_PASSWORD")
    gitlab_token = os.getenv("GITLAB_TOKEN")

    # Check if required environment variables are set
    if not all([argocd_server, argocd_username, argocd_password, gitlab_token]):
        raise ValueError("Missing required environment variables: ARGOCD_SERVER, ARGOCD_USERNAME, ARGOCD_PASSWORD, or GITLAB_TOKEN")

    # Create tmp directory if it doesn't exist
    os.makedirs("tmp", exist_ok=True)
    
    # Authenticate with ArgoCD
    argocd_login_cmd = f"argocd login {argocd_server} --username {argocd_username} --password {argocd_password} --grpc-web"
    run_command(argocd_login_cmd)

    # Define timestamp for dynamic file names
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    
    # List of commands with their respective output files
    commands = [
        ("kubectl get pods -A -o wide", "tmp/pre-experiment-pods.txt"),
        ("kubectl get nodes -o wide", "tmp/experiment-nodes.txt"),
        ("kubectl get svc -A", "tmp/experiment-svc.txt"),
        ("kubectl get all --all-namespaces -o yaml", "tmp/cluster-state-before.yaml"),
        ("kubectl get events --all-namespaces", "tmp/events-before.txt"),
        ("argocd-linux-amd64 app list -o json --grpc-web", "tmp/argocd-apps-state-before.json"),
        ("kubectl get applications.argoproj.io -A -o yaml", "tmp/argocd-applications.yaml"),
        (f"kubectl get nodes,pods,services,deployments,statefulsets,daemonsets,replicasets,jobs,cronjobs --all-namespaces -o wide", f"tmp/cluster-state-{timestamp}.txt"),
        (f"kubectl get all,configmap,secret,ingress,storageclass,persistentvolume,persistentvolumeclaim,namespace,role,rolebinding,clusterrole,clusterrolebinding,serviceaccount --all-namespaces -o yaml", f"tmp/all-manifests-{timestamp}.yaml")
    ]
    
    # Execute cluster info collection commands
    for cmd, outfile in commands:
        run_command(cmd, outfile)
    
    # Git operations
    git_repo_url = f"https://oauth2:{gitlab_token}@gitlab.fc.uralsibbank.ru/sre-platfom-support/sonarqube-00000.git"
    git_commands = [
        "git init --initial-branch=main",
        f"git remote add origin {git_repo_url} || git remote set-url origin {git_repo_url}",
        "git pull --rebase origin main",
        "git add tmp/*",
        f'git commit -m "Добавлены файлы состояния кластера {timestamp}" || true',
        "git push -u origin main"
    ]
    
    # Initialize Git and push to GitLab
    for cmd in git_commands:
        run_command(cmd)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Script failed: {e}")
        exit(1)
```
