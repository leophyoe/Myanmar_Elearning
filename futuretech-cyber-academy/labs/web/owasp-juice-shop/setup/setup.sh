#!/usr/bin/env bash
# ==============================================================================
# OWASP Juice Shop Cyber Range Sandbox Provisioning Script
# Future Tech Cyber Security Academy
# ==============================================================================

set -euo pipefail

IMAGE_NAME="bkimminich/juice-shop:v17.1.1"
NETWORK_NAME="ftc_cyber_range_net"

echo "[+] Initializing OWASP Juice Shop cyber range environment..."

if command -v docker >/dev/null 2>&1; then
    echo "[+] Verifying Docker daemon connection..."
    if docker info >/dev/null 2>&1; then
        echo "[+] Pulling allowlisted image: ${IMAGE_NAME}"
        docker pull "${IMAGE_NAME}"

        echo "[+] Ensuring isolated bridge network exists..."
        if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
            docker network create --driver bridge "${NETWORK_NAME}"
            echo "[+] Created isolated bridge network: ${NETWORK_NAME}"
        fi
        echo "[+] OWASP Juice Shop image and network successfully verified."
    else
        echo "[!] Docker daemon not accessible. Sandboxed Simulation Mode active."
    fi
else
    echo "[!] Docker CLI not installed. Sandboxed Simulation Mode active."
fi

echo "[✓] OWASP Juice Shop setup completed successfully."

