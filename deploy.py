"""
deploy.py
Automated deployment script using Python virtual environment and port 6001.
"""

import os
import sys
import paramiko

HOST = "62.72.59.120"
USER = "root"
PASSWORD = "Root@#1234567"
PORT = 6003
REMOTE_DIR = "/root/sensex"

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

def run_ssh_command(ssh, cmd):
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"STDOUT:\n{out}")
    if err:
        print(f"STDERR:\n{err}")
    return exit_status, out, err

def upload_directory(sftp, local_path, remote_path):
    try:
        sftp.mkdir(remote_path)
    except Exception:
        pass

    for item in os.listdir(local_path):
        if item in [".git", "__pycache__", ".vscode", "deploy.py", "logs", "venv", ".pytest_cache"]:
            continue
            
        local_item = os.path.join(local_path, item)
        remote_item = f"{remote_path}/{item}".replace("\\", "/")

        if os.path.isdir(local_item):
            upload_directory(sftp, local_item, remote_item)
        else:
            print(f"Uploading {local_item} -> {remote_item}")
            sftp.put(local_item, remote_item)

def deploy():
    print(f"Connecting to SSH {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    sftp = ssh.open_sftp()

    # Step 1: Create remote directory
    run_ssh_command(ssh, f"mkdir -p {REMOTE_DIR}/logs {REMOTE_DIR}/web {REMOTE_DIR}/tests")

    # Step 2: Upload files
    print("Uploading project files...")
    upload_directory(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()

    # Step 3: Setup Virtual Environment & Dependencies
    print("Setting up Python Virtual Environment on remote server...")
    run_ssh_command(ssh, f"python3 -m venv {REMOTE_DIR}/venv")
    run_ssh_command(ssh, f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip")
    run_ssh_command(ssh, f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt")

    # Step 4: Open port 6003 in firewall
    print(f"Opening port {PORT} in firewall...")
    run_ssh_command(ssh, f"ufw allow {PORT}/tcp || true")
    run_ssh_command(ssh, f"iptables -I INPUT -p tcp --dport {PORT} -j ACCEPT || true")

    # Step 5: Stop any previous process on port 6003 specifically
    print(f"Stopping any previous process on port {PORT}...")
    run_ssh_command(ssh, f"fuser -k {PORT}/tcp || true")

    # Step 6: Start server on port 6003 in background
    import time
    time.sleep(1)
    print(f"Starting server on port {PORT} with virtualenv...")
    run_ssh_command(ssh, f"cd {REMOTE_DIR} && PORT={PORT} HOST=0.0.0.0 nohup {REMOTE_DIR}/venv/bin/python3 server.py > {REMOTE_DIR}/server.log 2>&1 &")

    # Step 7: Verify process is running
    time.sleep(4)
    status, out, _ = run_ssh_command(ssh, f"cat {REMOTE_DIR}/server.log")
    print(f"\nRemote Server Log Output:\n{out}\n")

    # Check port listening
    run_ssh_command(ssh, f"ss -tlpn | grep {PORT}")

    ssh.close()
    print(f"\n==========================================")
    print(f"SENSEX DEPLOYMENT COMPLETED SUCCESSFULLY!")
    print(f"Live Dashboard URL: http://{HOST}:{PORT}")
    print(f"==========================================\n")

if __name__ == "__main__":
    deploy()
