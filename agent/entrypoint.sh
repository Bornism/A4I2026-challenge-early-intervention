#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export A4I_DATASET="${A4I_DATASET:-a4i_early_intervention}"
export A4I_LOCATION="${A4I_LOCATION:-US}"
export A4I_STATE="${A4I_STATE:-MS}"

# Start Google MCP Toolbox for Databases in the background when GOOGLE_CLOUD_PROJECT is set
if [[ -n "${GOOGLE_CLOUD_PROJECT:-}" ]] && command -v toolbox >/dev/null 2>&1; then
  RENDERED_TOOLS="/tmp/tools.rendered.yaml"
  sed "s/a4i_early_intervention/${A4I_DATASET}/g" /app/agent/tools.yaml > "${RENDERED_TOOLS}"

  echo "[entrypoint] Starting Google MCP Toolbox for Databases on 127.0.0.1:5000 (project=${GOOGLE_CLOUD_PROJECT}, dataset=${A4I_DATASET})..."
  toolbox --tools-file "${RENDERED_TOOLS}" --address 127.0.0.1 --port 5000 &

  # Wait briefly so ADK's ToolboxToolset sees port 5000 active at import time
  for _ in {1..15}; do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/toolset', timeout=0.5)" >/dev/null 2>&1; then
      echo "[entrypoint] MCP Toolbox ready on http://127.0.0.1:5000"
      break
    fi
    sleep 0.3
  done
fi

echo "[entrypoint] Starting First Milestones ADK + Workbench server on 0.0.0.0:${PORT}..."
exec uvicorn main:app --app-dir /app/agent --host 0.0.0.0 --port "${PORT}"
