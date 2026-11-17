#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================================="
echo "  LAUNCHING GOOGLE ADK WEB INTERACTIVE AGENT UI"
echo "  Challenge 04: Agents for Impact 2026"
echo "========================================================================="

export PYTHONPATH="/config/Desktop/AgentsForImpact/.venv/lib/python3.14/site-packages:$DIR:$PYTHONPATH"

PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}

echo "Starting ADK Web Server at http://${HOST}:${PORT} ..."
echo "Serving agents from: $DIR/agents"
echo "Press Ctrl+C to terminate."

/config/Desktop/AgentsForImpact/.venv/bin/adk web --host "$HOST" --port "$PORT" "$DIR/agents"
