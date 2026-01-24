#!/bin/bash
# Provision a Raspberry Pi to run the dashboard
# Usage: ./scripts/setup-pi.sh <ssh-host>
# Example: ./scripts/setup-pi.sh office-dashboard
set -e

PI_HOST="${1:-office-dashboard}"
REPO_URL="${2:-https://github.com/oldsj/home-dashboard.git}"

echo "Setting up dashboard on ${PI_HOST}..."

# Install dependencies
echo "Installing dependencies..."
ssh "${PI_HOST}" "sudo apt-get update -qq && sudo apt-get install -y -qq git curl"

# Install Docker (reinstall if missing or broken)
echo "Installing Docker..."
FRESH_DOCKER=$(ssh "${PI_HOST}" '
if docker compose version &>/dev/null && docker buildx version &>/dev/null; then
    echo "no"
else
    # Remove old/conflicting packages
    sudo apt-get remove -y $(dpkg --get-selections docker.io docker-compose docker-doc podman-docker containerd runc docker-buildx 2>/dev/null | cut -f1) 2>/dev/null || true
    # Install via convenience script then ensure all plugins
    curl -fsSL https://get.docker.com | sudo sh
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo "yes"
fi
')
ssh "${PI_HOST}" 'groups | grep -q docker || sudo usermod -aG docker $USER'

# Clone or update repo
echo "Setting up repository..."
ssh "${PI_HOST}" "
if [ -d ~/dashboard/.git ]; then
    cd ~/dashboard && git fetch origin && git reset --hard origin/main
else
    rm -rf ~/dashboard && git clone ${REPO_URL} ~/dashboard
fi
"

# Copy local credentials if they exist
if [[ -f config/credentials.yaml ]]; then
    echo "Copying credentials..."
    scp config/credentials.yaml "${PI_HOST}:~/dashboard/config/credentials.yaml"
fi

# Create systemd services
echo "Setting up systemd services..."
ssh "${PI_HOST}" 'sudo tee /etc/systemd/system/dashboard.service > /dev/null << EOF
[Unit]
Description=Home Dashboard
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/dashboard
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF'

ssh "${PI_HOST}" 'sudo tee /etc/systemd/system/dashboard-updater.service > /dev/null << EOF
[Unit]
Description=Dashboard Auto-Updater
After=dashboard.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/dashboard
ExecStart=/home/$USER/dashboard/scripts/update-loop.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF'

ssh "${PI_HOST}" "sudo systemctl daemon-reload && sudo systemctl enable dashboard dashboard-updater"

# Handle fresh Docker install vs update
if [[ "${FRESH_DOCKER}" == *"yes"* ]]; then
    echo ""
    echo "Fresh Docker install detected - rebooting for permissions..."
    ssh "${PI_HOST}" "sudo reboot" || true
    echo ""
    echo "Pi is rebooting. Dashboard will start automatically at:"
    echo "  http://${PI_HOST}:9753"
else
    echo "Starting services..."
    ssh "${PI_HOST}" "sudo systemctl restart dashboard dashboard-updater"
    echo ""
    echo "Setup complete!"
    echo "Dashboard will be at: http://${PI_HOST}:9753"
fi
