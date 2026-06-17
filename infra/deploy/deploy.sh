#!/usr/bin/env bash
set -euo pipefail

: "${EIDOLON_HOST:?Set EIDOLON_HOST}"
: "${EIDOLON_USER:?Set EIDOLON_USER}"
: "${EIDOLON_PATH:=/opt/eidolon}"

ssh "${EIDOLON_USER}@${EIDOLON_HOST}" "EIDOLON_PATH='${EIDOLON_PATH}' bash -s" <<'REMOTE'
set -euo pipefail
cd "${EIDOLON_PATH}"
git pull
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
alembic upgrade head
sudo systemctl restart eidolon-api
sudo systemctl status eidolon-api --no-pager
REMOTE
