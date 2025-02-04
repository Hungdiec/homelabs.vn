#!/bin/bash
# install.sh - Installer for DDNS Automate

set -e
# Ensure the installer is run from the repository root
REPO_ROOT="$(pwd)"

# Define service user and group (adjust as needed)
SERVICE_USER="$(whoami)"
SERVICE_GROUP="$(id -gn)"
TEMPLATE_FILE="$(pwd)/systemd/ddns.service.template"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Template file not found: $TEMPLATE_FILE"
    exit 1
fi

SERVICE_FILE="/tmp/ddns_service.service"
sed \
    -e "s|%REPO_ROOT%|${REPO_ROOT}|g" \
    -e "s|%SERVICE_USER%|${SERVICE_USER}|g" \
    -e "s|%SERVICE_GROUP%|${SERVICE_GROUP}|g" \
    "$TEMPLATE_FILE" > "$SERVICE_FILE"


# Ensure the script is run as root for installing system-wide services.
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (or with sudo): sudo bash install.sh"
    exit 1
fi

echo "Starting DDNS Automate installation..."

# === Step 1: Check and Install Prerequisites ===
if ! command -v python3 &>/dev/null; then
    echo "Python3 is not installed. Installing Python3..."
    apt-get update && apt-get install -y python3 || { echo "Installation failed. Please install Python3 manually."; exit 1; }
fi

if ! command -v pip3 &>/dev/null; then
    echo "pip3 is not installed. Installing pip3..."
    apt-get update && apt-get install -y python3-pip || { echo "Installation failed. Please install pip3 manually."; exit 1; }
fi

if ! python3 -m venv --help &>/dev/null; then
    echo "Python venv module is missing. Installing python3-venv..."
    apt-get update && apt-get install -y python3-venv || { echo "Installation failed. Please install python3-venv manually."; exit 1; }
fi
apt-get install -y python3
apt-get install -y python3-pip
apt-get install -y python3-venv
# === Step 2: Set Up Virtual Environment and Install Dependencies ===
# === Step 2: Set Up Virtual Environment and Install Dependencies ===
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate  # Ensure the virtual environment is activated
rm -rf venv

python3 -m venv venv
source venv/bin/activate
# Upgrade pip within the virtual environment
pip install --upgrade pip

echo "Installing Python dependencies..."
pip install -r requirements.txt



# === Step 3: Run the CLI Configuration Tool ===
echo "Starting configuration setup..."
python3 cli_config.py
# Install the ddns monitor script into /usr/local/bin
echo "Installing ddns monitor script..."
cp "$(pwd)/ddns/monitor_ddns.sh" /usr/local/bin/ddns_monitor.sh
chmod +x /usr/local/bin/ddns_monitor.sh


# === Step 4: Install the systemd Service ===
echo "Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/ddns.service
systemctl daemon-reload
systemctl enable ddns.service
systemctl start ddns.service

echo "Installation complete. The DDNS service is now running."
