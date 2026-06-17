#!/usr/bin/env bash
set -euo pipefail

# Example only. Review before running on a real server.

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib caddy git curl

# Ollama install command intentionally omitted from automated script.
# Install from official Ollama instructions on the target server.

echo "Create a non-root eidolon user, clone repo to /opt/eidolon, configure .env, install systemd service, and configure Caddy."
