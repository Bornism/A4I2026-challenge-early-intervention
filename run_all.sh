#!/usr/bin/env bash
set -e

echo "=== 1. Activating Python Virtual Environment ==="
source .venv/bin/activate

echo "=== 2. Running ADK Coordinator Triage Demonstration ==="
python repo_template/agent/run_coordinator.py

echo "=== 3. Starting Interactive Triage Web Dashboard on port 8080 ==="
echo "Navigate to http://localhost:8080 in your browser to view the live dashboard."
python repo_template/ui/server.py
