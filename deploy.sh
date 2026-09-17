#!/usr/bin/env bash
set -e

echo "=== [1/4] Checking environment prerequisites ==="
if ! command -v docker &> /dev/null; then
    echo "[-] Error: Docker is not installed. Please install Docker Engine first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "[-] Error: Docker Compose plugin not found."
    exit 1
fi

echo "=== [2/4] Initializing environment configuration ==="
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[!] .env not found, generating from .env.example..."
        cp .env.example .env
    else
        echo "[!] Creating default .env file..."
        cat << 'EOF' > .env
ADMIN_USER=admin
ADMIN_PASS=AdminPassword123!
SAMBA_DOMAIN=HOMELAB
SAMBA_REALM=HOMELAB.LAN
EOF
    fi
fi

# Ensure storage directories exist
mkdir -p storage/organized storage/watch

echo "=== [3/4] Building and launching core infrastructure ==="
docker compose pull || true
docker compose build --parallel
docker compose up -d

echo "=== [4/4] Health checking core endpoints ==="
sleep 10

endpoints=(
    "http://localhost:3000|Grafana"
    "http://localhost:9090|Prometheus"
    "http://localhost:9093|Alertmanager"
    "http://localhost:8080|Filebrowser"
    "http://localhost:9150/metrics|AD-Exporter"
)

for target in "${endpoints[@]}"; do
    IFS="|" read -r url name <<< "$target"
    if curl -s -f -o /dev/null --max-time 5 "$url"; then
        echo "[✔] $name is UP ($url)"
    else
        echo "[⚠] $name is not responding yet ($url)"
    fi
done

echo ""
echo "=== Hybrid Homelab Stack deployed successfully! ==="
echo "Grafana: http://localhost:3000 (Default: admin / admin)"
echo "Prometheus Targets: http://localhost:9090/targets"
echo "Filebrowser: http://localhost:8080"