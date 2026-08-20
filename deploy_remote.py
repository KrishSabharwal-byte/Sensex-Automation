"""
deploy_remote.py
Automated deployment script to deploy the BSE Sensex Trading Terminal to 62.72.59.120 on port 6003.
"""

import os
import sys
import paramiko

HOST = ""
USER = ""
PASS = ""
REMOTE_DIR = "/root/sensex_algo"
PORT = 6003

LOCAL_WORKSPACE = os.path.dirname(os.path.abspath(__file__))

def run_ssh_command(ssh, cmd):
    print(f"\n[REMOTE EXEC] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        sys.stdout.buffer.write(f"[OUT]\n{out.strip()}\n".encode('utf-8'))
    if err and exit_status != 0:
        sys.stdout.buffer.write(f"[ERR]\n{err.strip()}\n".encode('utf-8'))
    if exit_status != 0:
        raise RuntimeError(f"Command failed with exit code {exit_status}: {cmd}")
    return out

def upload_directory(sftp, local_dir, remote_dir):
    print(f"Uploading directory {local_dir} -> {remote_dir}")
    try:
        sftp.mkdir(remote_dir)
    except Exception:
        pass

    for item in os.listdir(local_dir):
        if item in ['.git', '.gemini', '__pycache__', '.pytest_cache', 'venv', '.venv', 'logs']:
            continue
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"

        if os.path.isdir(local_path):
            upload_directory(sftp, local_path, remote_path)
        else:
            print(f"  Uploading {item}...")
            sftp.put(local_path, remote_path)

def main():
    print(f"Connecting to {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("SSH Connection established.")

    # 1. Prepare Remote Directory
    run_ssh_command(ssh, f"mkdir -p {REMOTE_DIR}/logs")

    # 2. Upload Files via SFTP
    sftp = ssh.open_sftp()
    upload_directory(sftp, LOCAL_WORKSPACE, REMOTE_DIR)
    sftp.close()
    print("All files uploaded successfully.")

    # 3. Setup Python venv and install dependencies
    run_ssh_command(ssh, "apt-get update -y && apt-get install -y python3-venv python3-pip ufw")
    run_ssh_command(ssh, f"python3 -m venv {REMOTE_DIR}/venv")
    run_ssh_command(ssh, f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip")
    run_ssh_command(ssh, f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt")

    # 4. Configure Firewall (allow port 6003)
    run_ssh_command(ssh, f"ufw allow {PORT}/tcp || true")

    # 5. Create Systemd Service for persistent execution
    service_content = f"""[Unit]
Description=BSE Sensex Quantitative Trading Desk
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_DIR}
ExecStart={REMOTE_DIR}/venv/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port {PORT}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    sftp = ssh.open_sftp()
    with sftp.file("/etc/systemd/system/sensex.service", "w") as f:
        f.write(service_content)
    sftp.close()

    # 6. Enable and Start Service
    run_ssh_command(ssh, "systemctl daemon-reload")
    run_ssh_command(ssh, "systemctl enable sensex.service")
    run_ssh_command(ssh, "systemctl restart sensex.service")

    # 7. Check Status
    out = run_ssh_command(ssh, "systemctl status sensex.service --no-pager")
    print(f"\nDeployment Complete!\nService is active and running on http://{HOST}:{PORT}")

    ssh.close()

if __name__ == "__main__":
    main()
