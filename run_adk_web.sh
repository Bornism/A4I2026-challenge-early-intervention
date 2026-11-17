#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================================="
echo "  LAUNCHING GOOGLE ADK WEB INTERACTIVE AGENT UI"
echo "  Challenge 04: Agents for Impact 2026"
echo "========================================================================="

# 1. Use Google Cloud Project Vertex AI credentials directly (No API Key needed!)
export GOOGLE_GENAI_USE_VERTEXAI=True
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-5956a6cfcbdf}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

echo "Using Vertex AI with Project: $GOOGLE_CLOUD_PROJECT ($GOOGLE_CLOUD_LOCATION)"

# Load .env if present and has real key
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

if [ -n "$GEMINI_API_KEY" ] && [ "$GEMINI_API_KEY" != "your_gemini_api_key_here" ]; then
    # If user provided a key, verify it, otherwise unset so ADK uses Vertex AI
    if [[ ! "$GEMINI_API_KEY" =~ ^AIzaSy ]]; then
        echo "Note: Unsetting invalid GEMINI_API_KEY to use Google Cloud Vertex AI instead."
        unset GEMINI_API_KEY
    fi
else
    unset GEMINI_API_KEY
fi

export PYTHONPATH="/config/Desktop/AgentsForImpact/.venv/lib/python3.14/site-packages:$DIR:$PYTHONPATH"

PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}

echo "Starting ADK Web Server at http://${HOST}:${PORT} ..."
echo "Serving agents from: $DIR/agents"
echo "Press Ctrl+C to terminate."

/config/Desktop/AgentsForImpact/.venv/bin/adk web --host "$HOST" --port "$PORT" "$DIR/agents"
